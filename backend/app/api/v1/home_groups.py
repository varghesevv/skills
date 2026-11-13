import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.db import get_session
from app.models.church import Person
from app.schemas.church import IdName
from app.schemas.home_groups import LeaderChange, LeaderChanged
from app.services import succession
from app.services.succession import end_commit

router = APIRouter(prefix="/home-groups", tags=["home-groups"])

Admin = Annotated[Person, Depends(current_person("admin"))]


@router.put("/{group_id}/leader")
def change_leader(
    group_id: uuid.UUID,
    body: LeaderChange,
    admin: Admin,
    db: Annotated[Session, Depends(get_session)],
) -> LeaderChanged:
    """Replace the leader of a home group, or hand on your own, with a successor from its members
    (PENDING or above), in one transaction. The successor becomes a VERIFIER (unless higher); a
    stepping-down VERIFIER stays as a provider or a searcher, set by you, and nobody they admitted
    is flagged. An ADMIN of the group's church or the OWNER; `404` for any other. An ADMIN or the
    OWNER hand on only their own group, and keep their status (`former_leader_status: keep`)."""
    group = succession.replace_leader(
        db, admin, group_id, body.successor_id, body.former_leader_status
    )
    end_commit(db)
    leader = db.get(Person, group.leader_id)
    return LeaderChanged(
        group=IdName(id=group.id, name=group.name),
        leader=IdName(id=group.leader_id, name=(leader.full_name if leader else "") or ""),
    )
