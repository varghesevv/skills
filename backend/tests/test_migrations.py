import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.models import Base
from tests.conftest import MIGRATION_DB_NAME, alembic_config, ensure_database

pytestmark = pytest.mark.db


def test_upgrade_downgrade_roundtrip(base_database_url: str) -> None:
    url = ensure_database(base_database_url, MIGRATION_DB_NAME)
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(url)
    remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
    engine.dispose()
    assert remaining == set()

    command.upgrade(config, "head")


def test_models_match_migrations(base_database_url: str) -> None:
    """If this fails, a model changed without a matching Alembic migration (or vice versa)."""
    url = ensure_database(base_database_url, MIGRATION_DB_NAME)
    command.upgrade(alembic_config(url), "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()
    assert differences == []


def test_ready_endpoint_with_database(
    base_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.db import get_engine
    from app.main import app

    monkeypatch.setenv("DATABASE_URL", base_database_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        response = TestClient(app).get("/health/ready")
        assert response.status_code == 200
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
