"""Tables are created when the API starts on a database that has none, and only then."""

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.services.database_setup import create_tables_if_missing
from tests.conftest import alembic_config, ensure_database

pytestmark = pytest.mark.db

DB_NAME = "skills_startup_test"


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def _empty(url: str) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def test_an_empty_database_gets_every_table_then_is_left_alone(base_database_url: str) -> None:
    url = ensure_database(base_database_url, DB_NAME)
    _empty(url)
    assert create_tables_if_missing(url) is True
    tables = _tables(url)
    assert {"alembic_version", "people", "churches", "home_groups"} <= tables
    engine = create_engine(url)
    with engine.connect() as connection:
        head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    newest = ScriptDirectory.from_config(alembic_config(url)).get_current_head()
    assert head == newest
    # A second start changes nothing.
    assert create_tables_if_missing(url) is False


def test_a_database_with_tables_is_never_migrated_at_start_up(base_database_url: str) -> None:
    """An older revision stays where it is: on a server, deploy.sh migrates after a backup."""
    from alembic import command

    url = ensure_database(base_database_url, DB_NAME)
    _empty(url)
    older = ScriptDirectory.from_config(alembic_config(url)).get_revision("head").down_revision
    assert isinstance(older, str)
    command.upgrade(alembic_config(url), older)
    assert create_tables_if_missing(url) is False
    engine = create_engine(url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == older


def test_the_tests_do_not_create_tables_in_the_development_database() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert get_settings().create_tables_at_startup is False
