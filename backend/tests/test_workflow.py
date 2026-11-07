from copy import deepcopy
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from backend.app.models import Job
from backend.app.db import utcnow
from backend.app.schemas import Report
from backend.app.transcripts import segments_from_text, validate_report


TEXT = """Anna Weber: Heute besprechen wir die Vorbereitung des Kundentests.
Malik Brandt: Wir haben entschieden, den Test zuerst mit zwei Arbeitsplätzen durchzuführen.
Anna Weber: Ich erstelle die Checkliste bis 2026-11-12.
Malik Brandt: Ich prüfe die Zugänge bis Freitag.
Anna Weber: Welche Geräte benötigen wir zusätzlich? Das ist noch offen.
"""


def create(client):
    response = client.post(
        "/api/meetings",
        json={
            "title": "Kundentest",
            "meeting_date": "2026-11-04",
            "participants": ["Anna Weber", "Malik Brandt"],
            "reviewer_id": 2,
            "transcript": TEXT,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def process(client, meeting_id):
    with client.app.state.factory() as db:
        job = db.scalar(select(Job).where(Job.meeting_id == meeting_id).order_by(Job.created_at.desc()))
        job_id = job.id
    result = client.app.state.processor.run(job_id)
    assert result["state"] == "completed", result
    return job_id


def test_review_export_and_tasks(client):
    meeting = create(client)
    process(client, meeting)
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "draft"
    assert detail["revision"] == 1
    assert len(detail["report"]["tasks"]) == 2
    assert detail["report"]["tasks"][0]["due_date"] == "2026-11-12"
    assert detail["report"]["tasks"][1]["due_date"] is None
    assert client.get(f"/api/meetings/{meeting}/export/md").status_code == 409
    assert client.put(f"/api/meetings/{meeting}/tasks/A1", json={"revision": 1, "status": "done"}).status_code == 409
    assert client.post(f"/api/meetings/{meeting}/submit", json={"expected_revision": 1}).status_code == 200
    assert client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 1}).status_code == 403
    client.post("/api/login", json={"account_id": 2})
    assert client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 1}).status_code == 200
    export = client.get(f"/api/meetings/{meeting}/export/md")
    assert export.status_code == 200
    assert "Freigegeben von: Malik Brandt" in export.text
    assert "Quelle 3" in export.text
    assert client.put(f"/api/meetings/{meeting}/tasks/A1", json={"revision": 1, "status": "done"}).status_code == 200
    assert "done" in client.get(f"/api/meetings/{meeting}/export/csv").text
    assert client.get(f"/api/meetings/{meeting}").json()["task_states"]["A1"] == "done"


def test_private_access_and_session(client):
    meeting = create(client)
    client.post("/api/login", json={"account_id": 3})
    assert client.get("/api/meetings").json() == []
    assert client.get(f"/api/meetings/{meeting}").status_code == 404
    client.delete("/api/login")
    assert client.get("/api/meetings").status_code == 401
    assert (
        client.post("/api/login", json={"account_id": 1}, headers={"Origin": "https://elsewhere.invalid"}).status_code
        == 403
    )


def test_revisions_and_changes(client):
    meeting = create(client)
    process(client, meeting)
    detail = client.get(f"/api/meetings/{meeting}").json()
    body = {"expected_revision": 1, "report": detail["editable_report"]}
    body["report"]["summary"][0]["text"] = "Vorbereitung des Kundentests besprochen."
    assert client.put(f"/api/meetings/{meeting}/draft", json=body).status_code == 200
    assert client.put(f"/api/meetings/{meeting}/draft", json=body).status_code == 409
    assert (
        client.get(f"/api/meetings/{meeting}?revision=1").json()["report"]["summary"][0]["text"]
        != body["report"]["summary"][0]["text"]
    )
    client.post(f"/api/meetings/{meeting}/submit", json={"expected_revision": 2})
    client.post("/api/login", json={"account_id": 2})
    assert (
        client.post(
            f"/api/meetings/{meeting}/request-changes",
            json={"expected_revision": 2, "note": "Bitte offene Frage genauer formulieren."},
        ).status_code
        == 200
    )
    assert client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 2}).status_code == 409
    assert (
        client.put(
            f"/api/meetings/{meeting}/draft", json={"expected_revision": 2, "report": body["report"]}
        ).status_code
        == 403
    )


def test_source_replacement_fences_old_jobs(client):
    meeting = create(client)
    with client.app.state.factory() as db:
        job_id = db.scalar(select(Job.id).where(Job.meeting_id == meeting))
    start = client.app.state.processor.start(job_id)
    response = client.put(
        f"/api/meetings/{meeting}/source",
        json={
            "expected_source_version": 1,
            "transcript": TEXT + "Anna Weber: Wir ergänzen einen weiteren Testfall.",
            "external_processing_allowed": False,
        },
    )
    assert response.status_code == 200, response.text
    from backend.app.service import Conflict

    with pytest.raises(Conflict):
        client.app.state.processor.source(job_id, start["claim"])
    process(client, meeting)
    assert client.get(f"/api/meetings/{meeting}").json()["source"]["version"] == 2


def test_workflow_endpoints_and_idempotency(client):
    meeting = create(client)
    with client.app.state.factory() as db:
        job_id = db.scalar(select(Job.id).where(Job.meeting_id == meeting))
    assert client.post("/api/internal/start", json={"job_id": job_id}).status_code == 403
    headers = {"X-Workflow-Key": "test-key"}
    claim = client.post("/api/internal/start", json={"job_id": job_id}, headers=headers).json()["claim"]
    body = {"job_id": job_id, "claim": claim}
    assert client.post("/api/internal/save", json=body, headers=headers).status_code == 409
    for phase in ("source", "extract", "validate", "save", "save"):
        response = client.post(f"/api/internal/{phase}", json=body, headers=headers)
        assert response.status_code == 200, response.text
    assert len(client.get(f"/api/meetings/{meeting}").json()["versions"]) == 1


def test_quote_owner_deadline_validation():
    segments = segments_from_text(TEXT, ["Anna Weber", "Malik Brandt"])
    fields = {"text": "Checkliste erstellen", "quote": segments[2]["text"], "source_ids": [3]}
    report = Report(
        summary=[fields], decisions=[], tasks=[dict(fields, owner="Unbekannt", due_text="morgen")], open_questions=[]
    )
    checked = validate_report(report, segments, ["Anna Weber", "Malik Brandt"])
    assert checked["tasks"][0]["owner"] is None
    assert checked["tasks"][0]["due_text"] is None
    assert len(checked["warnings"]) == 2
    invalid = deepcopy(report.model_dump())
    invalid["summary"][0]["quote"] = "Eine erfundene Quelle"
    with pytest.raises(ValueError):
        validate_report(Report.model_validate(invalid), segments, ["Anna Weber"], manual=True)


def test_no_external_processing_without_consent(client):
    client.app.state.processor.settings.provider = "openai"
    response = client.post(
        "/api/meetings",
        json={
            "title": "Privat",
            "meeting_date": "2026-11-04",
            "participants": ["Anna Weber"],
            "reviewer_id": 2,
            "transcript": TEXT,
        },
    )
    assert response.status_code == 422


def test_failed_processing_can_retry(client, monkeypatch):
    meeting = create(client)
    processor = client.app.state.processor
    original = processor.extractor.extract
    monkeypatch.setattr(
        processor.extractor, "extract", lambda *args: (_ for _ in ()).throw(RuntimeError("private error"))
    )
    processor.tick()
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "error"
    assert "private error" not in detail["meeting"]["last_error"]
    monkeypatch.setattr(processor.extractor, "extract", original)
    assert client.post(f"/api/meetings/{meeting}/retry").status_code == 200
    processor.tick()
    assert client.get(f"/api/meetings/{meeting}").json()["meeting"]["status"] == "draft"


@pytest.mark.parametrize("failure", ["not_ready", "unavailable", "connection"])
def test_workflow_delivery_recovers_after_startup(client, monkeypatch, failure):
    meeting = create(client)
    processor = client.app.state.processor
    processor.settings.workflow_mode = "n8n"

    def unavailable(url, **kwargs):
        if failure == "connection":
            raise httpx.ConnectError("Connection unavailable")
        return httpx.Response(404 if failure == "not_ready" else 503, request=httpx.Request("POST", url))

    monkeypatch.setattr("backend.app.service.httpx.post", unavailable)
    processor.tick()
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "queued"
    assert detail["processing"]["state"] == "dispatched"
    with client.app.state.factory.begin() as db:
        job = db.scalar(select(Job).where(Job.meeting_id == meeting))
        job.lease_until = utcnow() - timedelta(seconds=1)

    def available(url, **kwargs):
        processor.run(kwargs["json"]["job_id"])
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("backend.app.service.httpx.post", available)
    processor.tick()
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "draft"
    assert len(detail["versions"]) == 1


def test_workflow_delivery_does_not_retry_invalid_credentials(client, monkeypatch):
    meeting = create(client)
    processor = client.app.state.processor
    processor.settings.workflow_mode = "n8n"
    monkeypatch.setattr(
        "backend.app.service.httpx.post",
        lambda url, **_: httpx.Response(403, request=httpx.Request("POST", url)),
    )
    processor.tick()
    assert client.get(f"/api/meetings/{meeting}").json()["meeting"]["status"] == "error"


def test_workflow_delivery_stops_after_three_attempts(client, monkeypatch):
    meeting = create(client)
    processor = client.app.state.processor
    processor.settings.workflow_mode = "n8n"
    deliveries = []

    def unavailable(url, **kwargs):
        deliveries.append(kwargs["json"]["job_id"])
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr("backend.app.service.httpx.post", unavailable)
    for _ in range(3):
        processor.tick()
        with client.app.state.factory.begin() as db:
            job = db.scalar(select(Job).where(Job.meeting_id == meeting))
            job.lease_until = utcnow() - timedelta(seconds=1)
    processor.tick()
    assert len(deliveries) == 3
    assert client.get(f"/api/meetings/{meeting}").json()["meeting"]["status"] == "error"
