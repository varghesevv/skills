from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    # Keep application loggers (and their handlers) alive when migrations run inside the app/tests.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# target_metadata also supplies the constraint naming convention to op.create_table().
target_metadata = Base.metadata


def _database_url() -> str:
    # Tests pass their own database through config.attributes; otherwise use the app settings.
    url = config.attributes.get("database_url")
    return str(url) if url else get_settings().require_database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
