from fastapi.testclient import TestClient
import pytest

from backend.app.config import Settings
from backend.app.main import build_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}", run_worker=False, workflow_token="test-key"
    )
    with TestClient(build_app(settings)) as client:
        client.post("/api/login", json={"account_id": 1})
        yield client
