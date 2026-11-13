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
from app.schemas.handover import (
    HandoverAccepted,
    HandoverCurrent,
    HandoverOut,
    HandoverPropose,
)
from app.services import church_invitations, closing, directory, handover

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


Admin = Annotated[Person, Depends(current_person("admin"))]


@router.post("/handover", status_code=status.HTTP_201_CREATED)
def propose_handover(
    body: HandoverPropose, owner: Owner, db: Annotated[Session, Depends(get_session)]
) -> HandoverOut:
    """Propose to hand the OWNER role to the ADMIN of another church. Name a new ADMIN for your own
    church and a new leader for your group (each may be left out only when nobody else is in the
    church or group, and you then keep that role). Nothing changes until the chosen ADMIN accepts;
    one proposal is open at a time (`409 handover_open`)."""
    request = handover.propose(
        db,
        owner,
        body.new_owner_id,
        body.successor_admin_id,
        body.successor_leader_id,
        body.former_owner_status,
    )
    return handover.view(db, request)


@router.get("/handover")
def current_handover(
    person: Admin, db: Annotated[Session, Depends(get_session)]
) -> HandoverCurrent:
    """The open proposal that concerns you (as the outgoing OWNER or the chosen ADMIN), if any."""
    request = handover.current(db, person)
    return HandoverCurrent(request=handover.view(db, request) if request else None)


@router.post("/handover/{request_id}/accept")
def accept_handover(
    request_id: uuid.UUID, person: Admin, db: Annotated[Session, Depends(get_session)]
) -> HandoverAccepted:
    """The chosen ADMIN accepts. In one transaction they become the OWNER (and stay the ADMIN of
    their own church), the OWNER's church gets its new ADMIN and its group its new leader, and the
    outgoing OWNER becomes a provider or a searcher (or keeps a role nobody can take over)."""
    return handover.accepted_view(db, handover.accept(db, person, request_id))


@router.post("/handover/{request_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_handover(
    request_id: uuid.UUID, person: Admin, db: Annotated[Session, Depends(get_session)]
) -> Response:
    """Either side withdraws an open proposal; the other side is told."""
    handover.cancel(db, person, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
