from datetime import timedelta
import logging
from pathlib import Path
import secrets
from uuid import uuid4

import httpx
from sqlalchemy import select, update

from .config import ROOT
from .db import utcnow
from .extraction import public_error
from .models import Audit, Job, Meeting, Revision, Source
from .schemas import Report
from .transcripts import segments_from_text, validate_report

log = logging.getLogger(__name__)


class Conflict(Exception):
    pass


def audit(db, meeting_id, kind, description, actor_id=None):
    db.add(Audit(meeting_id=meeting_id, actor_id=actor_id, kind=kind, description=description))


def queue(db, meeting):
    db.execute(
        update(Job)
        .where(Job.meeting_id == meeting.id, Job.state.in_(["pending", "dispatched", "processing"]))
        .values(state="cancelled", claim=None, lease_until=None)
    )
    job = Job(id=str(uuid4()), meeting_id=meeting.id, source_version=meeting.source_version)
    db.add(job)
    meeting.status, meeting.last_error, meeting.updated_at = "queued", None, utcnow()
    audit(db, meeting.id, "queued", f"Verarbeitung der Quelle {meeting.source_version} vorgemerkt.")
    return job


def private_audio(path):
    target = Path(path).resolve()
    directory = (ROOT / "data" / "uploads").resolve()
    if not target.is_relative_to(directory):
        raise ValueError("Die Aufnahme liegt nicht im vorgesehenen Speicher.")
    return target


class Processing:
    def __init__(self, factory, settings, extractor):
        self.factory, self.settings, self.extractor = factory, settings, extractor

    def tick(self):
        with self.factory.begin() as db:
            expired = db.scalars(
                select(Job).where(Job.state.in_(["processing", "dispatched"]), Job.lease_until < utcnow())
            ).all()
            for job in expired:
                job.state, job.claim = ("pending" if job.attempts < 3 else "failed"), None
                meeting = db.get(Meeting, job.meeting_id)
                if meeting.source_version == job.source_version:
                    meeting.status = "queued" if job.state == "pending" else "error"
                    meeting.last_error = "Unterbrochene Verarbeitung. Bitte den Verlauf prüfen."
                    audit(
                        db,
                        meeting.id,
                        "lease_expired",
                        "Erneuter Verarbeitungsversuch vorgemerkt."
                        if job.state == "pending"
                        else "Verarbeitung nach drei Versuchen abgebrochen.",
                    )
            ids = list(db.scalars(select(Job.id).where(Job.state == "pending").order_by(Job.created_at).limit(3)))
        for job_id in ids:
            if self.settings.workflow_mode == "local":
                self.run(job_id)
            else:
                self.dispatch(job_id)

    def dispatch(self, job_id):
        with self.factory.begin() as db:
            accepted = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.state == "pending")
                .values(
                    state="dispatched",
                    attempts=Job.attempts + 1,
                    lease_until=utcnow() + timedelta(seconds=30),
                )
            ).rowcount
            if not accepted:
                return
        try:
            if not self.settings.workflow_token:
                raise ValueError("Workflow-Zugang fehlt.")
            response = httpx.post(
                self.settings.n8n_webhook_url,
                json={"job_id": job_id},
                headers={"X-Workflow-Key": self.settings.workflow_token},
                timeout=8,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            if isinstance(error, httpx.RequestError) or (
                isinstance(error, httpx.HTTPStatusError)
                and error.response.status_code in (404, 408, 429, 500, 502, 503, 504)
            ):
                # Die bestehende Versandreservierung begrenzt Abstand und Anzahl der Wiederholungen.
                log.warning("Workflow delivery deferred for job %s (%s)", job_id, type(error).__name__)
                return
            self.fail(job_id, None)
        except ValueError:
            self.fail(job_id, None)

    def owned(self, db, job_id, claim):
        # Die Reservierung wird vor jedem Schritt gesperrt und verlängert.
        accepted = db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.state == "processing",
                Job.claim == claim,
                Job.lease_until > utcnow(),
            )
            .values(lease_until=utcnow() + timedelta(seconds=self.settings.lease_seconds))
        ).rowcount
        if not accepted:
            raise Conflict("Die Reservierung ist abgelaufen oder der Auftrag wurde bereits übernommen.")
        job = db.get(Job, job_id)
        meeting = db.get(Meeting, job.meeting_id)
        if meeting.source_version != job.source_version:
            raise Conflict("Es liegt inzwischen eine neuere Quelle vor.")
        source = db.scalar(select(Source).where(Source.meeting_id == meeting.id, Source.version == job.source_version))
        return job, meeting, source

    @staticmethod
    def snapshot(job, **extra):
        return {"job_id": job.id, "claim": job.claim, "state": job.state, "stage": job.stage, **extra}

    def start(self, job_id):
        with self.factory.begin() as db:
            job = db.get(Job, job_id)
            if not job:
                raise LookupError("Auftrag nicht gefunden.")
            pending = job.state == "pending"
            accepted = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.state.in_(["pending", "dispatched"]))
                .values(
                    state="processing",
                    stage="claimed",
                    claim=secrets.token_hex(32),
                    attempts=Job.attempts + (1 if pending else 0),
                    lease_until=utcnow() + timedelta(seconds=self.settings.lease_seconds),
                )
            ).rowcount
            if not accepted:
                return {"state": "already_claimed_or_finished", "job_id": job_id}
            meeting = db.get(Meeting, job.meeting_id)
            if meeting.source_version != job.source_version:
                job.state, job.claim = "cancelled", None
                return {"state": "cancelled", "job_id": job_id}
            if self.settings.provider == "openai" and not meeting.external_processing_allowed:
                job.state, meeting.status = "failed", "error"
                meeting.last_error = "Die externe Verarbeitung wurde nicht freigegeben."
                return {"state": "failed", "job_id": job_id}
            meeting.status, meeting.last_error = "processing", None
            audit(db, meeting.id, "started", "Verarbeitung übernommen.")
            return self.snapshot(job)

    def source(self, job_id, claim):
        with self.factory.begin() as db:
            job, meeting, source = self.owned(db, job_id, claim)
            if job.stage not in ("claimed", "source_ready"):
                raise Conflict("Zuerst muss die Quelle vorbereitet werden.")
            path = source.audio_path
            participants = meeting.participants
            if path:
                job.stage = "transcribing"
        if path:
            text = self.extractor.transcribe(private_audio(path))
            segments = segments_from_text(text, participants)
        else:
            segments = None
        with self.factory.begin() as db:
            job, meeting, source = self.owned(db, job_id, claim)
            if segments is not None:
                source.segments, source.audio_path = segments, None
            if not source.segments:
                raise ValueError("Die Quelle enthält keinen verarbeitbaren Text.")
            if job.stage in ("claimed", "transcribing"):
                audit(db, meeting.id, "source_ready", f"Quelle mit {len(source.segments)} Abschnitten vorbereitet.")
            job.stage = "source_ready"
            result = self.snapshot(job, segments=source.segments)
        if path:
            private_audio(path).unlink(missing_ok=True)
        return result

    def extract(self, job_id, claim):
        with self.factory.begin() as db:
            job, meeting, source = self.owned(db, job_id, claim)
            if job.raw_report is not None:
                job.stage = "extracted"
                return self.snapshot(job, report=job.raw_report)
            if job.stage != "source_ready":
                raise Conflict("Die Quelle ist noch nicht bereit oder wird bereits verarbeitet.")
            descriptor = {"title": meeting.title, "date": meeting.meeting_date, "participants": meeting.participants}
            segments = source.segments
            job.stage = "extracting"
        report = self.extractor.extract(descriptor, segments)
        report = Report.model_validate(report.model_dump())
        with self.factory.begin() as db:
            job, meeting, _ = self.owned(db, job_id, claim)
            if job.stage != "extracting":
                raise Conflict("Die Bearbeitung wurde inzwischen geändert.")
            job.raw_report, job.stage = report.model_dump(), "extracted"
            audit(db, meeting.id, "extracted", "Protokollinhalte aus der Quelle abgeleitet.")
            return self.snapshot(job, report=job.raw_report)

    def validate(self, job_id, claim):
        with self.factory.begin() as db:
            job, meeting, source = self.owned(db, job_id, claim)
            if job.checked_report is not None:
                job.stage = "validated"
                return self.snapshot(job, report=job.checked_report)
            if job.stage != "extracted":
                raise Conflict("Es liegt noch kein extrahiertes Protokoll vor.")
            report = validate_report(Report.model_validate(job.raw_report), source.segments, meeting.participants)
            job.checked_report, job.stage = report, "validated"
            audit(db, meeting.id, "validated", f"Quellen geprüft; {len(report['warnings'])} Prüfhinweise.")
            return self.snapshot(job, report=report)

    def save(self, job_id, claim):
        with self.factory.begin() as db:
            previous = db.get(Job, job_id)
            if previous and previous.state == "completed" and previous.claim == claim:
                return {"state": "completed", "job_id": job_id}
            job, meeting, _ = self.owned(db, job_id, claim)
            if job.stage != "validated":
                raise Conflict("Vor dem Speichern müssen die Quellen geprüft werden.")
            db.execute(
                update(Meeting)
                .where(Meeting.id == meeting.id, Meeting.source_version == job.source_version)
                .values(
                    current_revision=Meeting.current_revision + 1, status="draft", updated_at=utcnow(), last_error=None
                )
            )
            db.add(
                Revision(
                    meeting_id=meeting.id,
                    number=meeting.current_revision,
                    source_version=job.source_version,
                    report=job.checked_report,
                    editor_id=meeting.owner_id,
                )
            )
            job.state, job.stage, job.lease_until = "completed", "saved", None
            audit(
                db, meeting.id, "draft_saved", f"Entwurf {meeting.current_revision} gespeichert; Prüfung erforderlich."
            )
            return {"state": "completed", "job_id": job_id, "revision": meeting.current_revision}

    def fail(self, job_id, claim=None, error=None):
        message = (
            public_error(error)
            if error
            else "Ein Workflow-Schritt ist fehlgeschlagen. Ausführung und Backend-Verbindung prüfen."
        )
        with self.factory.begin() as db:
            conditions = (
                [Job.id == job_id, Job.state == "processing", Job.claim == claim]
                if claim
                else [
                    Job.id == job_id,
                    Job.state.in_(["pending", "dispatched"]),
                ]
            )
            accepted = db.execute(update(Job).where(*conditions).values(state="failed", lease_until=None)).rowcount
            if accepted:
                job = db.get(Job, job_id)
                meeting = db.get(Meeting, job.meeting_id)
                if meeting.source_version == job.source_version:
                    meeting.status, meeting.last_error = "error", message
                    audit(db, meeting.id, "error", message)
            return {"state": "failed" if accepted else "superseded", "job_id": job_id}

    def run(self, job_id):
        claim = None
        try:
            result = self.start(job_id)
            if result["state"] != "processing":
                return result
            claim = result["claim"]
            for phase in (self.source, self.extract, self.validate):
                phase(job_id, claim)
            return self.save(job_id, claim)
        except Conflict:
            return {"state": "superseded", "job_id": job_id}
        except Exception as error:
            log.warning("Processing failed for job %s (%s)", job_id, type(error).__name__)
            return self.fail(job_id, claim, error)
