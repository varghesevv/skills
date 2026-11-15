import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.db import get_session
from app.models.church import Person
from app.schemas.moves import MoveRequestCreate, MoveRequestList, MoveRequestOut
from app.services import moves

router = APIRouter(prefix="/move-requests", tags=["move-requests"])

Member = Annotated[Person, Depends(current_person("searcher"))]


@router.post("", status_code=status.HTTP_201_CREATED)
def ask(
    body: MoveRequestCreate, member: Member, db: Annotated[Session, Depends(get_session)]
) -> MoveRequestOut:
    """Ask to move to another home group of your church. Asking is your agreement; the leader of
    the group you leave and the leader of the group you join are told and must agree too. A leader
    steps down through succession before moving (`409 leads_a_group`)."""
    return moves.view(db, moves.request_move(db, member, body.home_group_id))


@router.get("")
def list_moves(
    member: Member,
    db: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> MoveRequestList:
    """The moves that concern you, as the member or as the leader of either group, newest first."""
    items, total = moves.listing(db, member, limit=limit, offset=offset)
    return MoveRequestList(items=items, total=total)


@router.post("/{request_id}/agree")
def agree(
    request_id: uuid.UUID, member: Member, db: Annotated[Session, Depends(get_session)]
) -> MoveRequestOut:
    """The leader of either group agrees (the member agreed by asking). The member moves in the
    same transaction as the last agreement. `404` for anyone it does not concern."""
    return moves.view(db, moves.agree(db, member, request_id))


@router.post("/{request_id}/cancel")
def cancel(
    request_id: uuid.UUID, member: Member, db: Annotated[Session, Depends(get_session)]
) -> MoveRequestOut:
    """The member or the leader of either group ends an open move; the other side is told."""
    return moves.view(db, moves.cancel(db, member, request_id))
