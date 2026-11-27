"""Creates the tables when the API starts on a database that has none (a new installation).

Only an empty database is touched: one without Alembic's `alembic_version` table. It is migrated to
the newest revision, so the initial config (app/services/initial_config.py) can be applied right
after. A database that already has tables is left alone: its migrations stay a deliberate step
(`alembic upgrade head` in docker-compose.yml locally, `infra/scripts/deploy.sh` on the server,
which takes a backup first and runs a destructive migration only with the owner's approval).
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, pool, text

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Several API processes may start together: one creates the tables, the others then see them.
_LOCK_KEY = "skills-create-tables"


def _alembic_config(database_url: str) -> Config:
    # Built in code, not from alembic.ini: that file's logging section would replace the app's
    # logging set-up (and its redaction of secrets) when migrations run inside the API.
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = database_url
    return config


def create_tables_if_missing(database_url: str) -> bool:
    """Migrate an empty database to the newest revision. Returns True when it did."""
    engine = create_engine(database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(hashtext(:key))"), {"key": _LOCK_KEY})
            try:
                if inspect(connection).has_table("alembic_version"):
                    return False
                logger.info("The database has no tables: creating them")
                command.upgrade(_alembic_config(database_url), "head")
                logger.info("Tables created")
                return True
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": _LOCK_KEY}
                )
                connection.commit()
    finally:
        engine.dispose()
