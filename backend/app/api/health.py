from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.db import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


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
