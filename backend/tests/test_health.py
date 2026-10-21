import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import get_engine
from app.main import app

client = TestClient(app)


def test_health_is_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_is_served() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Skills API"


def test_ready_reports_unavailable_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        response = TestClient(app).get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
