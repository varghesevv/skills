import os

import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.db


@pytest.mark.skipif("DATABASE_URL" not in os.environ, reason="DATABASE_URL not set")
def test_upgrade_and_downgrade() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.mark.skipif("DATABASE_URL" not in os.environ, reason="DATABASE_URL not set")
def test_ready_endpoint_with_database() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
