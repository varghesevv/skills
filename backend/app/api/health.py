from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.db import get_engine
from app.core.version import APP_VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Also tells which build is running."""
    return {"status": "ok", "version": APP_VERSION}


@router.get("/health/ready")
def ready() -> dict[str, str]:
    """Readiness: the database answers."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        # The detail is deliberately generic: connection errors can mention hosts and users.
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
