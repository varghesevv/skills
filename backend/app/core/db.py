from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # hide_parameters keeps bound values (which may be secrets or hashes) out of error messages.
    return create_engine(
        get_settings().require_database_url(), pool_pre_ping=True, hide_parameters=True
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
