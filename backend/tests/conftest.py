"""Shared fixtures. Database tests use their own databases, never the development one.

They need a PostgreSQL server reachable through DATABASE_URL (any database on it; only the
server and credentials are used). The user must be allowed to CREATE DATABASE.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# Non-secret settings the application requires from the environment. Tests supply them here;
# real environments get them from .env / the deployment. No secrets belong in this block.
for _name, _value in {
    "ENVIRONMENT": "ci",
    "CORS_ORIGINS": "http://localhost:5173",
    "REPORT_TIMEZONE": "Asia/Dubai",
}.items():
    os.environ.setdefault(_name, _value)

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_NAME = "skills_test"
MIGRATION_DB_NAME = "skills_migration_test"


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = database_url
    return config


def ensure_database(base_url: str, name: str) -> str:
    """Create the database if it does not exist yet; return its URL."""
    url = make_url(base_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return url.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def base_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


@pytest.fixture(scope="session")
def test_database_url(base_database_url: str) -> str:
    url = ensure_database(base_database_url, TEST_DB_NAME)
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    test_engine = create_engine(test_database_url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose changes are rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield db_session
    db_session.close()
    transaction.rollback()
    connection.close()
