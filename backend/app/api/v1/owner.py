import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.church import Person
from app.schemas.church_invitations import (
    ChurchInvitationCreated,
    ChurchInvitationList,
    ChurchInvite,
)
from app.services import church_invitations

router = APIRouter(prefix="/owner", tags=["owner"])

Owner = Annotated[Person, Depends(current_person("owner"))]


@router.post("/churches", status_code=status.HTTP_201_CREATED)
def invite_admin(
    body: ChurchInvite,
    owner: Owner,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChurchInvitationCreated:
    """Invite the ADMIN of a new church. The church exists once they accept. The link token is
    shown once; only a hash is kept. There is no mail service yet, so the OWNER shares the link."""
    invitation, token = church_invitations.invite(
        db, settings, owner, body.church_name, str(body.email)
    )
    return ChurchInvitationCreated(id=invitation.id, token=token, expires_at=invitation.expires_at)


@router.get("/churches/invitations")
def list_invitations(
    owner: Owner,
    db: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> ChurchInvitationList:
    """The undecided invitations, newest first. Paged: `limit` (1 to 100, default 50), `offset`."""
    items, total = church_invitations.pending(db, limit=limit, offset=offset)
    return ChurchInvitationList(items=items, total=total)


@router.delete("/churches/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invitation(
    invitation_id: uuid.UUID, owner: Owner, db: Annotated[Session, Depends(get_session)]
) -> Response:
    church_invitations.cancel(db, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
