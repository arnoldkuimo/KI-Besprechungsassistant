from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'meetings.db').as_posix()}"
    provider: Literal["demo", "openai"] = "demo"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    transcription_model: str = "gpt-transcribe"
    workflow_mode: Literal["local", "n8n"] = "local"
    workflow_token: str = ""
    n8n_webhook_url: str = "http://localhost:5680/webhook/meeting-notes"
    run_worker: bool = True
    worker_interval: float = 1
    lease_seconds: int = 240
    allowed_origins: list[str] = [
        "http://localhost:8030",
        "http://127.0.0.1:8030",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
