import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.church import Person
from app.schemas.signup import (
    GroupInvitationCreated,
    GroupInvitationList,
    GroupInvitationSummary,
)
from app.services import signup

router = APIRouter(prefix="/verifier", tags=["verifier"])

# A leader: VERIFIER or higher.
Verifier = Annotated[Person, Depends(current_person("verifier"))]


@router.post("/group-invitations", status_code=status.HTTP_201_CREATED)
def create_group_invitation(
    leader: Verifier,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GroupInvitationCreated:
    """A new link into your own home group. The token is shown once; only a hash is kept."""
    invitation, token = signup.create_group_invitation(db, settings, leader)
    return GroupInvitationCreated(id=invitation.id, token=token, expires_at=invitation.expires_at)


@router.get("/group-invitations")
def list_group_invitations(
    leader: Verifier, db: Annotated[Session, Depends(get_session)]
) -> GroupInvitationList:
    """The links into your home group that still work (the tokens are not shown again)."""
    return GroupInvitationList(
        items=[
            GroupInvitationSummary(id=i.id, created_at=i.created_at, expires_at=i.expires_at)
            for i in signup.active_invitations(db, leader)
        ]
    )


@router.delete("/group-invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_group_invitation(
    invitation_id: uuid.UUID, leader: Verifier, db: Annotated[Session, Depends(get_session)]
) -> Response:
    signup.revoke_invitation(db, leader, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
