import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.schemas.church import ChurchList, HomeGroupList
from app.services import directory
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/churches", tags=["churches"])

# Open to everyone (the sign-up screen has no account yet), so limited per IP address.
limiter = SlidingWindowLimiter(
    60, code="rate_limited", message="Too many requests. Try again in a moment."
)


def _limit(request: Request, settings: Settings) -> None:
    client = request.client.host if request.client else "unknown"
    limiter.check(client, settings.public_list_max_per_minute)


@router.get("")
def list_churches(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChurchList:
    """Public: the open churches by name. No contact details."""
    _limit(request, settings)
    return ChurchList(items=directory.open_churches(db))


@router.get("/{church_id}/home-groups")
def list_home_groups(
    church_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HomeGroupList:
    """Public: the open home groups of an open church, each with its leader's name."""
    _limit(request, settings)
    groups = directory.open_home_groups(db, church_id)
    if groups is None:
        raise ApiError(404, "not_found", "There is no such church")
    return HomeGroupList(items=groups)
