import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.db import get_session
from app.models.church import HomeGroup, Person
from app.schemas.church import IdName
from app.schemas.group_requests import (
    GroupRequestApprove,
    GroupRequestCreate,
    GroupRequestCreated,
    GroupRequestList,
    GroupStarted,
)
from app.services import group_requests

router = APIRouter(prefix="/group-requests", tags=["group-requests"])

Member = Annotated[Person, Depends(current_person("searcher"))]
Admin = Annotated[Person, Depends(current_person("admin"))]


def _group(group: HomeGroup) -> IdName:
    return IdName(id=group.id, name=group.name)


@router.post("", status_code=status.HTTP_201_CREATED)
def ask(
    body: GroupRequestCreate, member: Member, db: Annotated[Session, Depends(get_session)]
) -> GroupRequestCreated:
    """Ask to start a home group. An ADMIN or the OWNER start it at once, and the answer holds
    the group; if they lead a group now, `successor_id` names who leads it from now on (or it
    closes when they are its only member: `409 successor_required` otherwise)."""
    request, group = group_requests.request_group(db, member, body.group_name, body.successor_id)
    return GroupRequestCreated(
        request=group_requests.view(db, request), group=_group(group) if group else None
    )


@router.get("")
def list_requests(
    member: Member,
    db: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> GroupRequestList:
    """An ADMIN sees the open requests of their church, the OWNER of every church; everyone else
    their own requests. Paged: `limit` (1 to 100, default 50) and `offset`."""
    items, total = group_requests.listing(db, member, limit=limit, offset=offset)
    return GroupRequestList(items=items, total=total)


@router.post("/{request_id}/approve")
def approve(
    request_id: uuid.UUID,
    admin: Admin,
    db: Annotated[Session, Depends(get_session)],
    body: GroupRequestApprove | None = None,
) -> GroupStarted:
    """Create the group and move the requester in as its leader (a VERIFIER unless higher). If the
    requester leads a group now, `successor_id` names who leads it from now on, or the old group
    closes when the requester is its only member (`409 successor_required` otherwise)."""
    successor_id = body.successor_id if body else None
    return GroupStarted(group=_group(group_requests.approve(db, admin, request_id, successor_id)))


@router.post("/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline(
    request_id: uuid.UUID, admin: Admin, db: Annotated[Session, Depends(get_session)]
) -> Response:
    group_requests.decline(db, admin, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
