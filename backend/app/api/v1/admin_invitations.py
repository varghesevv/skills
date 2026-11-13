from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_address
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.schemas.church_invitations import (
    AdminAccepted,
    AdminInvitationAccept,
    AdminInvitationInfo,
    AdminInvitationLookup,
)
from app.services import church_invitations
from app.services.rate_limit import link_lookup_limiter, signup_limiter

router = APIRouter(prefix="/admin-invitations", tags=["admin-invitations"])


@router.post("/lookup")
def lookup(
    body: AdminInvitationLookup,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminInvitationInfo:
    """Public: the church and the domain the invitation went to. The token is in the body, so it
    never reaches an access log of the API. Rate limited per IP; every failure is the same `404`."""
    link_lookup_limiter.check(client_address(request), settings.link_lookup_max_per_hour)
    return church_invitations.info(db, body.token)


@router.post("/accept", status_code=status.HTTP_201_CREATED)
def accept(
    body: AdminInvitationAccept,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminAccepted:
    """Public: create the church, its first home group and its ADMIN, who leads it. The email
    address is the one invited. Rate limited per IP like sign-up."""
    signup_limiter.check(client_address(request), settings.signup_max_per_hour)
    admin = church_invitations.accept(db, body)
    return AdminAccepted(id=admin.id, church_id=admin.church_id, status=admin.status)
