from datetime import timedelta
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.config import Settings
from backend.app.db import utcnow
from backend.app.extraction import Extractor
from backend.app.main import build_app
from backend.app.models import Job
from backend.app.schemas import Report
from backend.app.service import Conflict
from backend.app.transcripts import segments_from_text
from test_workflow import TEXT, create, process


def test_approved_snapshot_remains_immutable(client):
    meeting = create(client)
    process(client, meeting)
    client.post(f"/api/meetings/{meeting}/submit", json={"expected_revision": 1})
    client.post("/api/login", json={"account_id": 2})
    client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 1})
    old = client.get(f"/api/meetings/{meeting}/export/md").text
    client.post("/api/login", json={"account_id": 1})
    report = client.get(f"/api/meetings/{meeting}").json()["editable_report"]
    report["summary"][0]["text"] = "Geänderte Zusammenfassung des Kundentests."
    response = client.put(f"/api/meetings/{meeting}/draft", json={"expected_revision": 1, "report": report})
    assert response.status_code == 200
    assert response.json()["current_revision"] == 2
    assert client.get(f"/api/meetings/{meeting}/export/md").status_code == 409
    assert client.get(f"/api/meetings/{meeting}/export/md?revision=1").text == old


def test_warnings_require_acknowledgement(client):
    meeting = create(client)
    processor = client.app.state.processor
    original = processor.extractor.extract

    def extract(*args):
        data = original(*args).model_dump()
        data["tasks"][0]["owner"] = "Erfundene Person"
        return Report.model_validate(data)

    processor.extractor.extract = extract
    process(client, meeting)
    client.post(f"/api/meetings/{meeting}/submit", json={"expected_revision": 1})
    client.post("/api/login", json={"account_id": 2})
    assert client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 1}).status_code == 422
    assert (
        client.post(
            f"/api/meetings/{meeting}/approve", json={"expected_revision": 1, "acknowledge_warnings": True}
        ).status_code
        == 200
    )


def test_expired_claim_cannot_save(client):
    meeting = create(client)
    processor = client.app.state.processor
    with client.app.state.factory() as db:
        job_id = db.scalar(select(Job.id).where(Job.meeting_id == meeting))
    claim = processor.start(job_id)["claim"]
    with client.app.state.factory.begin() as db:
        db.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
    with pytest.raises(Conflict):
        processor.source(job_id, claim)
    processor.tick()
    assert client.get(f"/api/meetings/{meeting}").json()["meeting"]["current_revision"] == 1


def test_manual_source_must_have_usable_text(client):
    meeting = create(client)
    response = client.put(
        f"/api/meetings/{meeting}/source",
        json={"expected_source_version": 1, "transcript": "\n" * 50, "external_processing_allowed": False},
    )
    assert response.status_code == 422


def test_spreadsheet_formulas_are_escaped(client):
    meeting = create(client)
    process(client, meeting)
    report = client.get(f"/api/meetings/{meeting}").json()["editable_report"]
    report["tasks"][0]["text"] = '=HYPERLINK("https://example.invalid")'
    client.put(f"/api/meetings/{meeting}/draft", json={"expected_revision": 1, "report": report})
    client.post(f"/api/meetings/{meeting}/submit", json={"expected_revision": 2})
    client.post("/api/login", json={"account_id": 2})
    client.post(f"/api/meetings/{meeting}/approve", json={"expected_revision": 2})
    content = client.get(f"/api/meetings/{meeting}/export/csv").text
    assert "'=HYPERLINK" in content


def test_openai_adapter_uses_schema_and_disables_storage(monkeypatch):
    captured = {}
    segments = segments_from_text(TEXT, ["Anna Weber", "Malik Brandt"])
    report = Extractor.demo(segments)

    class Client:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(parse=self.parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=report)

    monkeypatch.setattr("openai.OpenAI", Client)
    settings = Settings(_env_file=None, provider="openai", openai_api_key="test-only")
    result = Extractor(settings).extract({"title": "Test"}, segments)
    assert result == report
    assert captured["store"] is False
    assert captured["text_format"] is Report
    assert json.loads(captured["input"])["segments"] == segments


def test_audio_import_is_private_and_removed_after_transcription(tmp_path, monkeypatch):
    import backend.app.main as main
    import backend.app.service as service

    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setattr(service, "ROOT", tmp_path)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'audio.db'}",
        provider="openai",
        openai_api_key="test-only",
        run_worker=False,
    )
    extractor = SimpleNamespace(transcribe=lambda _: TEXT, extract=lambda _, segments: Extractor.demo(segments))
    with TestClient(build_app(settings, extractor)) as client:
        client.post("/api/login", json={"account_id": 1})
        metadata = {
            "title": "Aufnahme",
            "meeting_date": "2026-11-04",
            "participants": ["Anna Weber", "Malik Brandt"],
            "reviewer_id": 2,
            "external_processing_allowed": False,
        }
        wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 50

        def upload(data=wav):
            return client.post(
                "/api/meetings/audio",
                data={"metadata": json.dumps(metadata)},
                files={"file": ("../../aufzeichnung.wav", data, "audio/wav")},
            )

        assert upload().status_code == 422
        metadata["external_processing_allowed"] = True
        assert upload(b"invalid" * 10).status_code == 422
        response = upload()
        assert response.status_code == 201, response.text
        meeting = response.json()["id"]
        assert len(list((tmp_path / "data/uploads").glob("*.wav"))) == 1
        process(client, meeting)
        assert list((tmp_path / "data/uploads").glob("*.wav")) == []
        detail = client.get(f"/api/meetings/{meeting}").json()
        assert detail["report"]["tasks"]
        assert "audio_path" not in json.dumps(detail)


def test_workflow_export_has_authenticated_explicit_phases():
    from pathlib import Path

    workflow = json.loads(
        (Path(__file__).resolve().parents[2] / "workflows/meeting-notes.json").read_text(encoding="utf-8")
    )
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert nodes["webhook"]["parameters"]["authentication"] == "headerAuth"
    for phase in ("source", "extract", "validate", "save"):
        assert f"/api/internal/{phase}" in nodes[phase]["parameters"]["url"]
        assert nodes[phase]["credentials"]["httpHeaderAuth"]["id"] == "meetingBackend"
        assert nodes[phase]["onError"] == "continueErrorOutput"
