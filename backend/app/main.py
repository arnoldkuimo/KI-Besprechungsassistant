import csv
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import io
import logging
from pathlib import Path
import secrets
import threading
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select, update

from .config import ROOT, Settings
from .db import Base, database, utcnow
from .extraction import Extractor
from .models import Audit, Job, Meeting, Revision, Session, Source, TaskState, User
from .schemas import (
    Approval,
    ChangesRequested,
    DraftEdit,
    FailureInput,
    JobInput,
    Login,
    MeetingCreate,
    SourceEdit,
    StepInput,
    TaskUpdate,
    VersionInput,
)
from .service import Conflict, Processing, audit, private_audio, queue
from .transcripts import editable_report, segments_from_text, validate_report

log = logging.getLogger(__name__)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def stamp(value):
    return value.isoformat(timespec="seconds") + "Z" if value else None


def build_app(settings=None, extractor=None):
    settings = settings or Settings()
    engine, factory = database(settings.database_url)
    processor = Processing(factory, settings, extractor or Extractor(settings))
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            try:
                processor.tick()
            except Exception:
                log.warning("Background processing interrupted.")
            stop.wait(settings.worker_interval)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with factory.begin() as db:
            if not db.scalar(select(User.id).limit(1)):
                db.add_all(
                    [
                        User(id=1, name="Anna Weber", role="editor"),
                        User(id=2, name="Malik Brandt", role="reviewer"),
                        User(id=3, name="Nora Fischer", role="editor"),
                    ]
                )
        thread = None
        if settings.run_worker:
            thread = threading.Thread(target=worker, name="meeting-worker", daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=3)
        engine.dispose()

    app = FastAPI(title="Besprechungsprotokolle", version="1.0.0", lifespan=lifespan)
    app.state.factory, app.state.processor, app.state.settings = factory, processor, settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def headers(request, call_next):
        origin = request.headers.get("origin")
        if request.method in ("POST", "PUT", "DELETE") and origin and origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Diese Herkunft ist nicht zugelassen."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def session():
        with factory() as db:
            yield db

    def user(request: Request, db=Depends(session)):
        token = request.cookies.get("meeting_session")
        login = db.get(Session, digest(token)) if token else None
        person = db.get(User, login.user_id) if login and login.expires_at > utcnow() else None
        if not person:
            raise HTTPException(401, "Bitte anmelden.")
        return person

    def accessible(db, meeting_id, person):
        meeting = db.get(Meeting, meeting_id)
        if not meeting or person.id not in (meeting.owner_id, meeting.reviewer_id):
            raise HTTPException(404, "Besprechung nicht gefunden.")
        return meeting

    def owner(meeting, person):
        if person.id != meeting.owner_id:
            raise HTTPException(403, "Nur der Ersteller kann diesen Inhalt bearbeiten.")

    def record(db, meeting):
        return {
            "id": meeting.id,
            "title": meeting.title,
            "meeting_date": meeting.meeting_date,
            "participants": meeting.participants,
            "status": meeting.status,
            "source_version": meeting.source_version,
            "current_revision": meeting.current_revision,
            "approved_revision": meeting.approved_revision,
            "owner_id": meeting.owner_id,
            "reviewer_id": meeting.reviewer_id,
            "owner_name": db.get(User, meeting.owner_id).name,
            "reviewer_name": db.get(User, meeting.reviewer_id).name,
            "last_error": meeting.last_error,
            "created_at": stamp(meeting.created_at),
            "updated_at": stamp(meeting.updated_at),
        }

    def source_for(db, meeting_id, version):
        return db.scalar(select(Source).where(Source.meeting_id == meeting_id, Source.version == version))

    def revision_for(db, meeting_id, number):
        revision = db.scalar(select(Revision).where(Revision.meeting_id == meeting_id, Revision.number == number))
        if not revision:
            raise HTTPException(404, "Protokollversion nicht gefunden.")
        return revision

    def create(db, data, person, audio_path=None):
        if person.role != "editor":
            raise HTTPException(403, "Bitte ein Erstellerkonto wählen.")
        reviewer = db.get(User, data.reviewer_id)
        if not reviewer or reviewer.role != "reviewer" or reviewer.id == person.id:
            raise HTTPException(422, "Eine andere prüfende Person auswählen.")
        if settings.provider == "openai" and not data.external_processing_allowed:
            raise HTTPException(
                422, "Die Übertragung an den externen Verarbeitungsdienst muss ausdrücklich freigegeben sein."
            )
        if not audio_path and len(data.transcript.strip()) < 30:
            raise HTTPException(422, "Die Quelle muss mindestens 30 Zeichen enthalten.")
        segments = [] if audio_path else segments_from_text(data.transcript, data.participants)
        meeting = Meeting(
            title=data.title,
            meeting_date=data.meeting_date.isoformat(),
            participants=data.participants,
            owner_id=person.id,
            reviewer_id=reviewer.id,
            external_processing_allowed=data.external_processing_allowed,
        )
        db.add(meeting)
        db.flush()
        db.add(Source(meeting_id=meeting.id, version=1, segments=segments, audio_path=audio_path))
        audit(db, meeting.id, "created", "Besprechung und Quelle erfasst.", person.id)
        queue(db, meeting)
        db.commit()
        return record(db, meeting)

    @app.get("/api/health")
    def health(db=Depends(session)):
        db.execute(select(1))
        return {"ok": True}

    @app.get("/api/meta")
    def meta():
        return {
            "provider": settings.provider,
            "workflow_mode": settings.workflow_mode,
            "configured": bool(settings.openai_api_key),
            "demo_accounts": True,
        }

    @app.get("/api/accounts")
    def accounts(db=Depends(session)):
        return [{"id": p.id, "name": p.name, "role": p.role} for p in db.scalars(select(User).order_by(User.id))]

    @app.post("/api/login")
    def login(data: Login, response: Response, request: Request, db=Depends(session)):
        person = db.get(User, data.account_id)
        if not person:
            raise HTTPException(404, "Konto nicht gefunden.")
        previous = request.cookies.get("meeting_session")
        if previous:
            db.execute(delete(Session).where(Session.token_hash == digest(previous)))
        token = secrets.token_urlsafe(32)
        db.add(Session(token_hash=digest(token), user_id=person.id, expires_at=utcnow() + timedelta(hours=8)))
        db.commit()
        response.set_cookie("meeting_session", token, httponly=True, samesite="lax", max_age=28800)
        return {"id": person.id, "name": person.name, "role": person.role}

    @app.get("/api/me")
    def me(person=Depends(user)):
        return {"id": person.id, "name": person.name, "role": person.role}

    @app.delete("/api/login")
    def logout(request: Request, response: Response, db=Depends(session)):
        token = request.cookies.get("meeting_session")
        if token:
            db.execute(delete(Session).where(Session.token_hash == digest(token)))
        db.commit()
        response.delete_cookie("meeting_session")
        return {"ok": True}

    @app.get("/api/meetings")
    def meetings(person=Depends(user), db=Depends(session)):
        query = select(Meeting).where((Meeting.owner_id == person.id) | (Meeting.reviewer_id == person.id))
        return [record(db, m) for m in db.scalars(query.order_by(Meeting.updated_at.desc()).limit(200))]

    @app.post("/api/meetings", status_code=201)
    def new_meeting(data: MeetingCreate, person=Depends(user), db=Depends(session)):
        try:
            return create(db, data, person)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/meetings/audio", status_code=201)
    async def audio(metadata: str = Form(...), file: UploadFile = File(...), person=Depends(user), db=Depends(session)):
        if settings.provider != "openai" or not settings.openai_api_key:
            raise HTTPException(422, "Audio benötigt einen konfigurierten externen Transkriptionsdienst.")
        try:
            data = MeetingCreate.model_validate_json(metadata)
        except ValueError:
            raise HTTPException(422, "Ungültige Besprechungsdaten.") from None
        if not data.external_processing_allowed:
            raise HTTPException(422, "Die Verarbeitung der Aufnahme muss ausdrücklich freigegeben sein.")
        extension = Path(file.filename or "").suffix.lower()
        if extension not in (".wav", ".mp3", ".m4a", ".webm", ".ogg"):
            raise HTTPException(422, "Unterstützt werden WAV, MP3, M4A, WebM und OGG.")
        directory = ROOT / "data" / "uploads"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (str(uuid4()) + extension)
        length = 0
        try:
            with target.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    length += len(chunk)
                    if length > 25 * 1024 * 1024:
                        raise HTTPException(413, "Die Aufnahme darf höchstens 25 MB groß sein.")
                    output.write(chunk)
            if length < 44:
                raise HTTPException(422, "Die Aufnahme ist leer oder zu kurz.")
            with target.open("rb") as uploaded:
                header = uploaded.read(16)
            valid = {
                ".wav": header.startswith(b"RIFF") and header[8:12] == b"WAVE",
                ".mp3": header.startswith(b"ID3") or (header[0] == 0xFF and header[1] & 0xE0 == 0xE0),
                ".m4a": header[4:8] == b"ftyp",
                ".webm": header.startswith(b"\x1a\x45\xdf\xa3"),
                ".ogg": header.startswith(b"OggS"),
            }
            if not valid[extension]:
                raise HTTPException(422, "Dateiinhalt und Aufnahmeformat passen nicht zusammen.")
            return create(db, data, person, str(target))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.get("/api/meetings/{meeting_id}")
    def detail(
        meeting_id: int, revision: int | None = Query(default=None, ge=1), person=Depends(user), db=Depends(session)
    ):
        meeting = accessible(db, meeting_id, person)
        selected = revision or meeting.current_revision
        version = revision_for(db, meeting.id, selected) if selected else None
        source = source_for(db, meeting.id, version.source_version if version else meeting.source_version)
        current_source = source_for(db, meeting.id, meeting.source_version)
        versions = list(
            db.scalars(select(Revision).where(Revision.meeting_id == meeting.id).order_by(Revision.number.desc()))
        )
        events = list(db.scalars(select(Audit).where(Audit.meeting_id == meeting.id).order_by(Audit.id)))
        states = {
            s.task_id: s.status
            for s in db.scalars(
                select(TaskState).where(TaskState.meeting_id == meeting.id, TaskState.revision == selected)
            )
        }
        job = db.scalar(select(Job).where(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()).limit(1))
        return {
            "meeting": record(db, meeting),
            "report": version.report if version else None,
            "revision": selected,
            "approved": bool(version and version.approved_by),
            "approved_by": db.get(User, version.approved_by).name if version and version.approved_by else None,
            "approved_at": stamp(version.approved_at) if version else None,
            "editable_report": editable_report(version.report) if version else None,
            "source": {"version": source.version, "segments": source.segments},
            "current_source": {"version": current_source.version, "segments": current_source.segments},
            "versions": [
                {"number": v.number, "approved": bool(v.approved_by), "created_at": stamp(v.created_at)}
                for v in versions
            ],
            "task_states": states,
            "events": [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "description": e.description,
                    "actor": db.get(User, e.actor_id).name if e.actor_id else "Verarbeitung",
                    "created_at": stamp(e.created_at),
                }
                for e in events
            ],
            "processing": {"stage": job.stage, "state": job.state, "mode": settings.workflow_mode} if job else None,
        }

    @app.put("/api/meetings/{meeting_id}/source")
    def source_edit(meeting_id: int, data: SourceEdit, person=Depends(user), db=Depends(session)):
        meeting = accessible(db, meeting_id, person)
        owner(meeting, person)
        if settings.provider == "openai" and not data.external_processing_allowed:
            raise HTTPException(422, "Die externe Verarbeitung muss erneut bestätigt werden.")
        try:
            segments = segments_from_text(data.transcript, meeting.participants)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        old_source = source_for(db, meeting.id, meeting.source_version)
        old_audio = old_source.audio_path
        changed = db.execute(
            update(Meeting)
            .where(Meeting.id == meeting.id, Meeting.source_version == data.expected_source_version)
            .values(
                source_version=Meeting.source_version + 1, external_processing_allowed=data.external_processing_allowed
            )
        ).rowcount
        if not changed:
            raise HTTPException(409, "Die Quelle wurde inzwischen geändert. Bitte neu laden.")
        db.add(Source(meeting_id=meeting.id, version=meeting.source_version, segments=segments))
        queue(db, meeting)
        audit(
            db,
            meeting.id,
            "source_changed",
            f"Neue Quelle {meeting.source_version} erfasst; ältere Versionen bleiben erhalten.",
            person.id,
        )
        db.commit()
        if old_audio:
            private_audio(old_audio).unlink(missing_ok=True)
        return record(db, meeting)

    @app.put("/api/meetings/{meeting_id}/draft")
    def edit(meeting_id: int, data: DraftEdit, person=Depends(user), db=Depends(session)):
        meeting = accessible(db, meeting_id, person)
        owner(meeting, person)
        current = revision_for(db, meeting.id, data.expected_revision)
        source = source_for(db, meeting.id, current.source_version)
        try:
            checked = validate_report(data.report, source.segments, meeting.participants, manual=True)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        changed = db.execute(
            update(Meeting)
            .where(
                Meeting.id == meeting.id,
                Meeting.current_revision == data.expected_revision,
                Meeting.status.in_(["draft", "changes_requested", "approved"]),
            )
            .values(current_revision=Meeting.current_revision + 1, status="draft", updated_at=utcnow())
        ).rowcount
        if not changed:
            raise HTTPException(409, "Dieser Stand kann nicht mehr bearbeitet werden. Bitte neu laden.")
        db.add(
            Revision(
                meeting_id=meeting.id,
                number=meeting.current_revision,
                source_version=current.source_version,
                report=checked,
                editor_id=person.id,
            )
        )
        audit(db, meeting.id, "edited", f"Entwurf als Version {meeting.current_revision} bearbeitet.", person.id)
        db.commit()
        return record(db, meeting)

    @app.post("/api/meetings/{meeting_id}/submit")
    def submit(meeting_id: int, data: VersionInput, person=Depends(user), db=Depends(session)):
        meeting = accessible(db, meeting_id, person)
        owner(meeting, person)
        changed = db.execute(
            update(Meeting)
            .where(
                Meeting.id == meeting.id,
                Meeting.current_revision == data.expected_revision,
                Meeting.status.in_(["draft", "changes_requested"]),
            )
            .values(status="review", updated_at=utcnow())
        ).rowcount
        if not changed:
            raise HTTPException(409, "Es liegt kein aktueller Entwurf zur Einreichung vor.")
        audit(db, meeting.id, "submitted", f"Version {data.expected_revision} zur Prüfung eingereicht.", person.id)
        db.commit()
        return record(db, meeting)

    def reviewing(db, meeting_id, expected, person):
        meeting = accessible(db, meeting_id, person)
        if person.id != meeting.reviewer_id:
            raise HTTPException(403, "Nur die zugewiesene prüfende Person kann entscheiden.")
        if meeting.current_revision != expected or meeting.status != "review":
            raise HTTPException(409, "Diese Version liegt nicht mehr zur Prüfung vor.")
        return meeting

    @app.post("/api/meetings/{meeting_id}/approve")
    def approve(meeting_id: int, data: Approval, person=Depends(user), db=Depends(session)):
        meeting = reviewing(db, meeting_id, data.expected_revision, person)
        version = revision_for(db, meeting.id, data.expected_revision)
        if version.report["warnings"] and not data.acknowledge_warnings:
            raise HTTPException(422, "Die Prüfhinweise müssen vor der Freigabe ausdrücklich geprüft werden.")
        changed = db.execute(
            update(Meeting)
            .where(
                Meeting.id == meeting.id, Meeting.current_revision == data.expected_revision, Meeting.status == "review"
            )
            .values(status="approved", approved_revision=data.expected_revision, updated_at=utcnow())
        ).rowcount
        if not changed:
            raise HTTPException(409, "Der Stand wurde inzwischen geändert.")
        version.approved_by, version.approved_at = person.id, utcnow()
        audit(db, meeting.id, "approved", f"Version {version.number} freigegeben.", person.id)
        db.commit()
        return record(db, meeting)

    @app.post("/api/meetings/{meeting_id}/request-changes")
    def changes(meeting_id: int, data: ChangesRequested, person=Depends(user), db=Depends(session)):
        meeting = reviewing(db, meeting_id, data.expected_revision, person)
        changed = db.execute(
            update(Meeting)
            .where(
                Meeting.id == meeting.id, Meeting.current_revision == data.expected_revision, Meeting.status == "review"
            )
            .values(status="changes_requested", updated_at=utcnow())
        ).rowcount
        if not changed:
            raise HTTPException(409, "Der Stand wurde inzwischen geändert.")
        audit(db, meeting.id, "changes_requested", data.note, person.id)
        db.commit()
        return record(db, meeting)

    @app.post("/api/meetings/{meeting_id}/retry")
    def retry(meeting_id: int, person=Depends(user), db=Depends(session)):
        meeting = accessible(db, meeting_id, person)
        owner(meeting, person)
        if meeting.status != "error":
            raise HTTPException(409, "Nur eine fehlgeschlagene Verarbeitung kann erneut gestartet werden.")
        queue(db, meeting)
        db.commit()
        return record(db, meeting)

    @app.put("/api/meetings/{meeting_id}/tasks/{task_id}")
    def task_update(meeting_id: int, task_id: str, data: TaskUpdate, person=Depends(user), db=Depends(session)):
        meeting = accessible(db, meeting_id, person)
        version = revision_for(db, meeting.id, data.revision)
        if not version.approved_by:
            raise HTTPException(409, "Aufgaben können erst nach der Freigabe nachverfolgt werden.")
        if not any(t["id"] == task_id for t in version.report["tasks"]):
            raise HTTPException(404, "Aufgabe nicht gefunden.")
        db.execute(update(Meeting).where(Meeting.id == meeting.id).values(updated_at=utcnow()))
        state = db.scalar(
            select(TaskState).where(
                TaskState.meeting_id == meeting.id, TaskState.revision == version.number, TaskState.task_id == task_id
            )
        )
        if state:
            state.status = data.status
        else:
            db.add(TaskState(meeting_id=meeting.id, revision=version.number, task_id=task_id, status=data.status))
        audit(
            db, meeting.id, "task_updated", f"Aufgabe {task_id} in Version {version.number}: {data.status}.", person.id
        )
        db.commit()
        return {"task_id": task_id, "status": data.status}

    @app.get("/api/meetings/{meeting_id}/export/{format}")
    def export(
        meeting_id: int,
        format: str,
        revision: int | None = Query(default=None, ge=1),
        person=Depends(user),
        db=Depends(session),
    ):
        meeting = accessible(db, meeting_id, person)
        version = revision_for(db, meeting.id, revision or meeting.current_revision)
        if not version.approved_by:
            raise HTTPException(409, "Diese Version wurde noch nicht freigegeben.")
        if format == "csv":
            stream = io.StringIO(newline="")
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Aufgabe", "Verantwortlich", "Frist", "Datum", "Status", "Quellen"])
            for task in version.report["tasks"]:
                state = db.scalar(
                    select(TaskState).where(
                        TaskState.meeting_id == meeting.id,
                        TaskState.revision == version.number,
                        TaskState.task_id == task["id"],
                    )
                )
                row = [
                    task["text"],
                    task["owner"] or "",
                    task["due_text"] or "",
                    task["due_date"] or "",
                    state.status if state else "open",
                    ",".join(map(str, task["source_ids"])),
                ]
                writer.writerow(
                    ["'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row]
                )
            body, media = "\ufeff" + stream.getvalue(), "text/csv; charset=utf-8"
        elif format == "md":

            def escape(text):
                return (
                    str(text)
                    .replace("\n", " ")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("[", "\\[")
                    .replace("]", "\\]")
                )

            lines = [
                f"# {escape(meeting.title)}",
                f"Datum: {meeting.meeting_date}",
                f"Version: {version.number}",
                f"Freigegeben von: {db.get(User, version.approved_by).name}",
                "",
            ]
            for key, label in (
                ("summary", "Zusammenfassung"),
                ("decisions", "Entscheidungen"),
                ("tasks", "Aufgaben"),
                ("open_questions", "Offene Fragen"),
            ):
                lines += [f"## {label}"]
                for item in version.report[key]:
                    extra = (
                        f" · {item['owner'] or 'Nicht benannt'} · {item['due_text'] or 'Keine Frist'}"
                        if key == "tasks"
                        else ""
                    )
                    lines += [
                        f"- {escape(item['text'])}{escape(extra)} (Quelle {', '.join(map(str, item['source_ids']))})",
                        f"  Beleg: {escape(item['quote'])}",
                    ]
                if not version.report[key]:
                    lines.append("Keine Einträge.")
                lines.append("")
            body, media = "\n".join(lines), "text/markdown; charset=utf-8"
        else:
            raise HTTPException(404, "Exportformat nicht verfügbar.")
        return Response(
            content=body,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="protokoll-{meeting.id}-v{version.number}.{format}"'
            },
        )

    def workflow_auth(x_workflow_key: str = Header(default="")):
        if (
            not x_workflow_key
            or not settings.workflow_token
            or not secrets.compare_digest(x_workflow_key.encode(), settings.workflow_token.encode())
        ):
            raise HTTPException(403, "Workflow-Zugang ungültig.")

    @app.post("/api/internal/start", dependencies=[Depends(workflow_auth)])
    def start_job(data: JobInput):
        try:
            return processor.start(data.job_id)
        except LookupError:
            raise HTTPException(404, "Auftrag nicht gefunden.") from None

    def workflow_endpoint(phase):
        def execute(data: StepInput):
            try:
                return getattr(processor, phase)(data.job_id, data.claim)
            except Conflict as error:
                raise HTTPException(409, str(error)) from None
            except Exception as error:
                processor.fail(data.job_id, data.claim, error)
                raise HTTPException(
                    503, "Verarbeitungsschritt fehlgeschlagen. Den Besprechungsverlauf prüfen."
                ) from None

        execute.__name__ = f"workflow_{phase}"
        return execute

    for phase in ("source", "extract", "validate", "save"):
        app.add_api_route(
            f"/api/internal/{phase}", workflow_endpoint(phase), methods=["POST"], dependencies=[Depends(workflow_auth)]
        )

    @app.post("/api/internal/fail", dependencies=[Depends(workflow_auth)])
    def failed(data: FailureInput):
        return processor.fail(data.job_id, data.claim)

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        if (dist / "assets").exists():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


app = build_app()
