import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.db import get_session
from app.models.church import Person
from app.schemas.church import IdName
from app.schemas.home_groups import GroupClose, GroupClosed, LeaderChange, LeaderChanged
from app.services import closing, succession
from app.services.succession import end_commit

router = APIRouter(prefix="/home-groups", tags=["home-groups"])

Admin = Annotated[Person, Depends(current_person("admin"))]
Leader = Annotated[Person, Depends(current_person("verifier"))]


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


@router.post("/{group_id}/close")
def close_group(
    group_id: uuid.UUID,
    body: GroupClose,
    leader: Leader,
    db: Annotated[Session, Depends(get_session)],
) -> GroupClosed:
    """The leader of a home group closes it, being its last member (`409 group_not_empty`
    otherwise), by moving into another open group of the church, in one transaction. A VERIFIER
    becomes a provider or a searcher, recorded as set by the church's ADMIN; an ADMIN or the OWNER
    keeps their status (`former_leader_status: keep`). The group is kept, with the date it closed,
    and links to it and moves into it end. `404` for anyone but its leader."""
    closed, joined = closing.close_group(
        db, leader, group_id, body.move_to_group_id, body.former_leader_status
    )
    closing.commit(db)
    me = db.get(Person, leader.id)
    return GroupClosed(
        closed_group=IdName(id=closed.id, name=closed.name),
        joined_group=IdName(id=joined.id, name=joined.name),
        status=me.status if me else leader.status,
    )
