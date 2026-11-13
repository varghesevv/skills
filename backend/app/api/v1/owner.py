import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.church import Person
from app.schemas.church_invitations import (
    ChurchClosed,
    ChurchInvitationCreated,
    ChurchInvitationList,
    ChurchInvite,
    ChurchListOwner,
)
from app.services import church_invitations, closing, directory

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


@router.get("/churches")
def list_churches(
    owner: Owner,
    db: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> ChurchListOwner:
    """Every church (open ones first), with its ADMIN and counts of open groups, members and
    revoked people. Paged: `limit` (1 to 100, default 50), `offset`."""
    items, total = directory.owner_churches(db, limit=limit, offset=offset)
    return ChurchListOwner(items=items, total=total)


@router.post("/churches/{church_id}/close")
def close_church(
    church_id: uuid.UUID, owner: Owner, db: Annotated[Session, Depends(get_session)]
) -> ChurchClosed:
    """Close a church other than your own: it, all its home groups and all its members' accounts
    are closed together and kept, with the date, for the history. Nobody is revoked or flagged;
    the church's revoked people stay on its list, so they still cannot sign up again. Former
    members sign up again in another church. `409 owner_church` for the OWNER's own church."""
    church, groups, accounts = closing.close_church(db, owner, church_id)
    closing.commit(db)
    return ChurchClosed(
        id=church.id, name=church.name, closed_groups=groups, closed_accounts=accounts
    )
