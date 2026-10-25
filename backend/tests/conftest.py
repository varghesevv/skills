"""Shared fixtures. Database tests use their own databases, never the development one.

They need a PostgreSQL server reachable through DATABASE_URL (any database on it; only the
server and credentials are used). The user must be allowed to CREATE DATABASE.
"""

import os
import secrets
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# Non-secret settings the application requires from the environment. Tests supply them here;
# real environments get them from .env / the deployment. No secrets belong in this block.
for _name, _value in {
    "ENVIRONMENT": "ci",
    "CORS_ORIGINS": "http://localhost:5173",
    "REPORT_TIMEZONE": "Asia/Dubai",
    "FRONTEND_BASE_URL": "http://localhost:5173",
    "ACCESS_TOKEN_MINUTES": "15",
    "REFRESH_TOKEN_DAYS": "30",
    "RESET_TOKEN_MINUTES": "60",
    "LOGIN_MAX_FAILURES": "5",
    "LOGIN_WINDOW_MINUTES": "15",
    "REPORTS_OUTPUT_DIR": str(Path(tempfile.gettempdir()) / "skills-test-reports"),
}.items():
    os.environ.setdefault(_name, _value)
# Small reveal limits so the tests can reach them. Set directly, not with setdefault, because
# the shell or docker compose may already provide the (larger) defaults.
os.environ["REVEAL_MAX_PER_HOUR"] = "3"
os.environ["REVEAL_MAX_PER_DAY"] = "5"
# A random signing key for this test run only; nothing secret is stored in the source.
os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))

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


@pytest.fixture
def client(session: Session) -> Iterator["TestClient"]:
    """An API client whose requests use the rolled-back test session."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.db import get_session
    from app.main import app

    get_settings.cache_clear()

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override
    # A fixed client address, so login throttling (per email and IP) is predictable.
    with TestClient(app, client=("203.0.113.7", 50000)) as test_client:
        yield test_client
    app.dependency_overrides.clear()
