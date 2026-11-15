import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.models import Base
from tests.conftest import MIGRATION_DB_NAME, alembic_config, ensure_database
from tests.trust_helpers import World

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


def test_removing_the_older_accounts_keeps_people_and_what_hangs_on_them(
    base_database_url: str,
) -> None:
    """Migration 0018 drops the older tables and gives the authentication tables to people."""
    url = ensure_database(base_database_url, MIGRATION_DB_NAME)
    config = alembic_config(url)
    command.downgrade(config, "base")
    command.upgrade(config, "0017")
    engine = create_engine(url)
    unknown = uuid.uuid4()
    with Session(engine) as session, session.begin():
        world = World(session)
        owner = world.owner.id
        provider = world.add_person("provider").id
        session.execute(
            text(
                "INSERT INTO freelancers (user_email, mobile_number, password_hash) "
                "VALUES ('old@example.com', '+971500000001', 'x')"
            )
        )
        session.execute(
            text(
                "INSERT INTO login_history (user_type, user_id, login_email, succeeded) VALUES "
                "('person', :owner, 'a@example.com', true), "
                "('person', :unknown, 'b@example.com', false), "
                "('workhost', NULL, 'c@example.com', false)"
            ),
            {"owner": owner, "unknown": unknown},
        )
        session.execute(
            text(
                "INSERT INTO refresh_tokens (user_type, user_id, token_hash, expires_at) VALUES "
                "('person', :owner, 'h1', now() + interval '1 day'), "
                "('freelancer', :unknown, 'h2', now() + interval '1 day'), "
                "('person', :unknown, 'h3', now() + interval '1 day')"
            ),
            {"owner": owner, "unknown": unknown},
        )
        session.execute(
            text(
                "INSERT INTO password_reset_tokens (user_type, user_id, token_hash, expires_at) "
                "VALUES ('person', :owner, 'r1', now() + interval '1 day'), "
                "('organisation', :unknown, 'r2', now() + interval '1 day')"
            ),
            {"owner": owner, "unknown": unknown},
        )
        session.execute(
            text(
                "INSERT INTO person_phone_reveals (revealer_id, provider_id, channel, source) "
                "VALUES (:owner, :provider, 'show', 'detail')"
            ),
            {"owner": owner, "provider": provider},
        )

    command.upgrade(config, "head")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for gone in (
        "freelancers",
        "work_hosts",
        "organisations",
        "admins",
        "org_freelancers",
        "user_ratings",
        "freelancer_labels",
        "freelancer_unavailability",
        "person_phone_reveals",
    ):
        assert gone not in tables, gone
    assert "phone_reveals" in tables
    for table in ("login_history", "refresh_tokens", "password_reset_tokens"):
        assert "user_type" not in {c["name"] for c in inspector.get_columns(table)}
    with engine.connect() as connection:

        def count(sql: str) -> int:
            return int(connection.execute(text(sql)).scalar_one())

        assert count("SELECT count(*) FROM login_history") == 2  # the older kind is gone
        assert count("SELECT count(*) FROM login_history WHERE user_id IS NULL") == 1
        assert count("SELECT count(*) FROM refresh_tokens") == 1
        assert count("SELECT count(*) FROM password_reset_tokens") == 1
        assert count("SELECT count(*) FROM phone_reveals") == 1
        assert count("SELECT count(*) FROM people") == 2

    # Going back recreates the older tables (empty) and keeps what people have.
    command.downgrade(config, "0017")
    inspector = inspect(engine)
    assert {"freelancers", "organisations", "person_phone_reveals"} <= set(
        inspector.get_table_names()
    )
    with engine.connect() as connection:
        kinds = connection.execute(text("SELECT DISTINCT user_type FROM refresh_tokens")).all()
        assert [row[0] for row in kinds] == ["person"]
        assert connection.execute(text("SELECT count(*) FROM freelancers")).scalar_one() == 0
    engine.dispose()
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
