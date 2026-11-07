import json
from types import SimpleNamespace

import httpx
from openai import APIConnectionError, AuthenticationError, RateLimitError
import pytest

from backend.app.config import Settings
from backend.app.extraction import Extractor, public_error
from backend.app.schemas import Report
from backend.app.transcripts import segments_from_text, validate_report
from test_workflow import TEXT, create


def test_missing_key_does_not_create_meeting(client):
    client.app.state.settings.provider = "openai"
    response = client.post(
        "/api/meetings",
        json={
            "title": "Kundentest",
            "meeting_date": "2026-11-07",
            "participants": ["Anna Weber"],
            "reviewer_id": 2,
            "transcript": TEXT,
            "external_processing_allowed": True,
        },
    )
    assert response.status_code == 503
    assert client.get("/api/meetings").json() == []


@pytest.mark.parametrize("kind", ["missing", "invalid"])
def test_unusable_model_output_is_not_saved(client, monkeypatch, kind):
    meeting = create(client)

    class Client:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(parse=self.parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def parse(self, **kwargs):
            if kind == "invalid":
                return SimpleNamespace(output_parsed=SimpleNamespace(model_dump=lambda: {"summary": []}))
            return SimpleNamespace(output_parsed=None)

    monkeypatch.setattr("openai.OpenAI", Client)
    processor = client.app.state.processor
    processor.extractor = Extractor(Settings(_env_file=None, provider="openai", openai_api_key="test-only"))
    processor.tick()
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "error"
    assert detail["report"] is None
    assert detail["versions"] == []
    assert "test-only" not in json.dumps(detail)
    assert client.get(f"/api/meetings/{meeting}/export/md").status_code == 404


def test_transcription_adapter_uses_configured_model_and_file(tmp_path, monkeypatch):
    path = tmp_path / "test.wav"
    path.write_bytes(b"RIFF" + bytes(100))
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self.transcribe))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def transcribe(self, **kwargs):
            captured.update(kwargs)
            assert kwargs["file"].read().startswith(b"RIFF")
            return SimpleNamespace(text=TEXT)

    monkeypatch.setattr("openai.OpenAI", Client)
    settings = Settings(_env_file=None, provider="openai", openai_api_key="test-only", transcription_model="test-model")
    assert Extractor(settings).transcribe(path) == TEXT
    assert captured["model"] == "test-model"
    assert captured["response_format"] == "json"
    assert captured["file"].closed


def test_invalid_model_quotes_do_not_become_protocol():
    segments = segments_from_text(TEXT, ["Anna Weber", "Malik Brandt"])
    report = Extractor.demo(segments).model_dump()
    report["summary"][0]["quote"] = "Eine nicht besprochene Aussage."
    checked = validate_report(Report.model_validate(report), segments, ["Anna Weber", "Malik Brandt"])
    assert len(checked["summary"]) == len(report["summary"]) - 1
    assert checked["warnings"]


@pytest.mark.parametrize("kind", ["auth", "quota", "connection"])
def test_api_errors_do_not_expose_private_messages(kind):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    errors = {
        "auth": AuthenticationError("private-key-value", response=httpx.Response(401, request=request), body=None),
        "quota": RateLimitError("private-key-value", response=httpx.Response(429, request=request), body=None),
        "connection": APIConnectionError(request=request, message="private-key-value"),
    }
    assert "private-key-value" not in public_error(errors[kind])


def test_source_check_and_review_still_required_with_openai_adapter(client, monkeypatch):
    segments = segments_from_text(TEXT, ["Anna Weber", "Malik Brandt"])
    report = Extractor.demo(segments)

    class Client:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(parse=lambda **_: SimpleNamespace(output_parsed=report))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("openai.OpenAI", Client)
    settings = client.app.state.settings
    settings.provider, settings.openai_api_key = "openai", "test-only"
    response = client.post(
        "/api/meetings",
        json={
            "title": "Kundentest",
            "meeting_date": "2026-11-07",
            "participants": ["Anna Weber", "Malik Brandt"],
            "reviewer_id": 2,
            "transcript": TEXT,
            "external_processing_allowed": True,
        },
    )
    assert response.status_code == 201
    meeting = response.json()["id"]
    client.app.state.processor.tick()
    detail = client.get(f"/api/meetings/{meeting}").json()
    assert detail["meeting"]["status"] == "draft"
    assert detail["approved"] is False
    assert client.get(f"/api/meetings/{meeting}/export/md").status_code == 409
