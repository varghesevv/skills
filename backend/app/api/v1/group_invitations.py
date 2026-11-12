from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.schemas.signup import GroupInvitationInfo
from app.services import signup
from app.services.rate_limit import link_lookup_limiter

router = APIRouter(prefix="/group-invitations", tags=["group-invitations"])


@router.get("/{token}")
def group_invitation(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GroupInvitationInfo:
    """Public: the church and group a link leads to, for the sign-up screen. Rate limited per IP;
    every failure (no such link, expired, revoked, group closed) is the same `404`."""
    client = request.client.host if request.client else "unknown"
    link_lookup_limiter.check(client, settings.link_lookup_max_per_hour)
    info = signup.invitation_info(db, token)
    if info is None:
        raise ApiError(404, "not_found", "This link is not valid")
    return info
