"""Moving between home groups of one church (docs/verification.md, "Home group leaders", step 4).

An admitted member who does not lead a group asks to move to another group of their church. The
move happens, in the same transaction, when three people agree: the member (by asking), the leader
of the group they leave and the leader of the group they join. The ADMIN or the OWNER can also move
a member directly. A leader moves only after stepping down through succession.

Moving into a group takes a shared lock on both groups, after the people, so a group cannot close
at the moment someone moves in (`signup.open_group`, `succession.end_leadership`).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.trust import MoveRequest, Notification
from app.schemas.church import IdName
from app.schemas.moves import MoveAgreements, Moved, MoveRequestOut
from app.services.locks import lock_people

MOVE_REQUESTED = "move_requested"  # notification kind: a member asks to move out or in (leaders)
MOVE_COMPLETED = "move_completed"  # notification kind: you were moved to another group
MOVE_CANCELLED = "move_cancelled"  # notification kind: a move request was cancelled
MEMBER_MOVED_IN = "member_moved_in"  # notification kind: a member joined your group
MEMBER_MOVED_OUT = "member_moved_out"  # notification kind: a member left your group

MEMBER = ("searcher", "provider", "verifier", "admin", "owner")  # admitted: not PENDING or revoked


def _state(request: MoveRequest) -> str:
    if request.completed_at is not None:
        return "completed"
    return "cancelled" if request.cancelled_at is not None else "open"


def _leads(db: Session, person: Person) -> bool:
    group = db.get(HomeGroup, person.home_group_id) if person.home_group_id else None
    return group is not None and group.closed_at is None and group.leader_id == person.id


def _open_groups(db: Session, from_id: uuid.UUID, to_id: uuid.UUID) -> tuple[HomeGroup, HomeGroup]:
    """Both groups, locked for sharing (in id order), if they are open and of one church."""
    ids = sorted({from_id, to_id}, key=str)
    groups = {
        g.id: g
        for g in (
            db.get(HomeGroup, i, with_for_update={"read": True}, populate_existing=True)
            for i in ids
        )
        if g is not None
    }
    source, target = groups.get(from_id), groups.get(to_id)
    if (
        source is None
        or target is None
        or source.closed_at is not None
        or target.closed_at is not None
    ):
        raise ApiError(422, "invalid_choice", "That home group is not available")
    church = db.get(Church, target.church_id)
    if church is None or church.closed_at is not None or source.church_id != target.church_id:
        raise ApiError(422, "invalid_choice", "That home group is not available")
    return source, target


def _check_can_move(db: Session, person: Person) -> HomeGroup:
    """The person is an admitted member of an open group and leads nothing. Returns the group."""
    if person.closed_at is not None or person.status not in MEMBER or person.home_group_id is None:
        raise ApiError(403, "not_admitted", "Only an admitted member can move")
    if _leads(db, person):
        raise ApiError(409, "leads_a_group", "A leader steps down through succession before moving")
    group = db.get(HomeGroup, person.home_group_id)
    if group is None:
        raise ApiError(409, "state_changed", "This person changed meanwhile. Reload.")
    return group


def _notify(db: Session, person_id: uuid.UUID, kind: str, subject_id: uuid.UUID) -> None:
    db.add(Notification(person_id=person_id, kind=kind, subject_id=subject_id))


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # Only the one-open-request index means "you already have a move waiting"; any other
        # constraint (a row that changed at the same moment) is a state to reload.
        diag = getattr(error.orig, "diag", None)
        if getattr(diag, "constraint_name", None) == "uq_move_requests_one_open":
            raise ApiError(409, "request_open", "You already have a move waiting") from None
        raise ApiError(
            409, "state_changed", "Something changed meanwhile. Reload and try again."
        ) from None


def _has_open_request(db: Session, person: Person) -> bool:
    return (
        db.scalar(
            select(MoveRequest.id).where(
                MoveRequest.person_id == person.id,
                MoveRequest.completed_at.is_(None),
                MoveRequest.cancelled_at.is_(None),
            )
        )
        is not None
    )


def request_move(db: Session, person: Person, to_group_id: uuid.UUID) -> MoveRequest:
    db.refresh(person, with_for_update=True)
    source = _check_can_move(db, person)
    _, target = _open_groups(db, source.id, to_group_id)
    if source.id == target.id:
        raise ApiError(422, "invalid_choice", "That is the group you belong to")
    if _has_open_request(db, person):
        raise ApiError(409, "request_open", "You already have a move waiting")
    request = MoveRequest(
        person_id=person.id,
        from_group_id=source.id,
        to_group_id=target.id,
        agreed_by_person_at=datetime.now(UTC),  # asking is agreeing
    )
    db.add(request)
    for leader_id in {source.leader_id, target.leader_id}:
        _notify(db, leader_id, MOVE_REQUESTED, person.id)
    _commit(db)
    return request


def _locked_request(
    db: Session, actor: Person, request_id: uuid.UUID
) -> tuple[MoveRequest, Person, HomeGroup, HomeGroup]:
    """Lock what a decision on the request touches, and return it if the actor is one of the three
    (the member, or the current leader of either group). Anyone else gets `404`."""
    found = db.get(MoveRequest, request_id)
    if found is None:
        raise ApiError(404, "not_found", "There is no such move")
    groups = [db.get(HomeGroup, found.from_group_id), db.get(HomeGroup, found.to_group_id)]
    if any(g is None for g in groups):
        raise ApiError(404, "not_found", "There is no such move")
    ids = [actor.id, found.person_id, *(g.leader_id for g in groups if g is not None)]
    people = lock_people(db, ids)
    request = db.get(MoveRequest, request_id, with_for_update=True, populate_existing=True)
    mover = people.get(found.person_id)
    source = db.get(
        HomeGroup, found.from_group_id, with_for_update={"read": True}, populate_existing=True
    )
    target = db.get(
        HomeGroup, found.to_group_id, with_for_update={"read": True}, populate_existing=True
    )
    if request is None or mover is None or source is None or target is None:
        raise ApiError(404, "not_found", "There is no such move")
    concerned = actor.id in (mover.id, source.leader_id, target.leader_id)
    if not concerned:
        raise ApiError(404, "not_found", "There is no such move")
    return request, mover, source, target


def agree(db: Session, actor: Person, request_id: uuid.UUID) -> MoveRequest:
    request, mover, source, target = _locked_request(db, actor, request_id)
    if _state(request) != "open":
        raise ApiError(409, "not_open", "This move has been decided")
    now = datetime.now(UTC)
    if actor.id == source.leader_id and request.agreed_by_from_leader_at is None:
        request.agreed_by_from_leader_at = now
    elif actor.id == target.leader_id and request.agreed_by_to_leader_at is None:
        request.agreed_by_to_leader_at = now
    elif actor.id == mover.id and request.agreed_by_person_at is None:
        request.agreed_by_person_at = now
    else:
        raise ApiError(409, "already_agreed", "You have already agreed to this move")
    if (
        request.agreed_by_person_at is not None
        and request.agreed_by_from_leader_at is not None
        and request.agreed_by_to_leader_at is not None
    ):
        _check_still_possible(db, request, mover, source, target)
        _perform(db, mover, source, target, actor, finished=request.id)
        request.completed_at = now
    _commit(db)
    return request


def _check_still_possible(
    db: Session, request: MoveRequest, mover: Person, source: HomeGroup, target: HomeGroup
) -> None:
    """What was true when the move was asked for must still be true when the last one agrees."""
    if (
        mover.closed_at is not None
        or mover.status not in MEMBER
        or mover.home_group_id != source.id
    ):
        raise ApiError(
            409, "request_stale", "The member is no longer in the group they asked to leave"
        )
    if _leads(db, mover):
        raise ApiError(409, "leads_a_group", "A leader steps down through succession before moving")
    if source.closed_at is not None or target.closed_at is not None:
        raise ApiError(409, "request_stale", "A home group of this move has closed")


def _perform(
    db: Session,
    mover: Person,
    source: HomeGroup,
    target: HomeGroup,
    actor: Person,
    finished: uuid.UUID | None = None,
) -> None:
    """Move the member and tell everyone it concerns. Not a change of status: no history row.
    `finished` is the request this move completes; every other open request of theirs is for a
    move from where they no longer are, and is cancelled."""
    mover.home_group_id = target.id
    _notify(db, mover.id, MOVE_COMPLETED, actor.id)
    if source.leader_id != actor.id:
        _notify(db, source.leader_id, MEMBER_MOVED_OUT, mover.id)
    if target.leader_id != actor.id:
        _notify(db, target.leader_id, MEMBER_MOVED_IN, mover.id)
    others = db.scalars(
        select(MoveRequest).where(
            MoveRequest.person_id == mover.id,
            MoveRequest.completed_at.is_(None),
            MoveRequest.cancelled_at.is_(None),
            *([MoveRequest.id != finished] if finished is not None else []),
        )
    ).all()
    for other in others:
        other.cancelled_at = datetime.now(UTC)
        for group_id in (other.from_group_id, other.to_group_id):
            leader = db.get(HomeGroup, group_id)
            if leader is not None and leader.leader_id != actor.id:
                _notify(db, leader.leader_id, MOVE_CANCELLED, mover.id)


def cancel(db: Session, actor: Person, request_id: uuid.UUID) -> MoveRequest:
    request, mover, source, target = _locked_request(db, actor, request_id)
    if _state(request) != "open":
        raise ApiError(409, "not_open", "This move has been decided")
    request.cancelled_at = datetime.now(UTC)
    if actor.id != mover.id:
        _notify(db, mover.id, MOVE_CANCELLED, actor.id)
    else:
        for leader_id in {source.leader_id, target.leader_id}:
            _notify(db, leader_id, MOVE_CANCELLED, mover.id)
    _commit(db)
    return request


def move_directly(
    db: Session, actor: Person, person_id: uuid.UUID, to_group_id: uuid.UUID
) -> Person:
    """An ADMIN (within their church) or the OWNER moves a member to another group of the church."""
    people = lock_people(db, [actor.id, person_id])
    mover = people.get(person_id)
    locked_actor = people.get(actor.id)
    if (
        locked_actor is None
        or locked_actor.closed_at is not None
        or locked_actor.status not in ("admin", "owner")
    ):
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    if (
        mover is None
        or mover.closed_at is not None
        or mover.id == actor.id
        or (locked_actor.status == "admin" and mover.church_id != locked_actor.church_id)
    ):
        raise ApiError(404, "not_found", "There is no such person")
    source = _check_can_move(db, mover)
    _, target = _open_groups(db, source.id, to_group_id)
    if source.id == target.id:
        raise ApiError(422, "invalid_choice", "That is the group they belong to")
    _perform(db, mover, source, target, locked_actor)
    _commit(db)
    return mover


def moved_view(db: Session, person: Person) -> Moved:
    group = db.get(HomeGroup, person.home_group_id) if person.home_group_id else None
    if group is None:  # cannot happen: a member who just moved belongs to the new group
        raise ApiError(409, "state_changed", "This person changed meanwhile. Reload.")
    return Moved(
        person=IdName(id=person.id, name=person.full_name or ""),
        home_group=IdName(id=group.id, name=group.name),
    )


def _view(db: Session, requests: list[MoveRequest]) -> list[MoveRequestOut]:
    people = {
        p.id: p
        for p in db.scalars(select(Person).where(Person.id.in_({r.person_id for r in requests})))
    }
    group_ids = {r.from_group_id for r in requests} | {r.to_group_id for r in requests}
    groups = {g.id: g for g in db.scalars(select(HomeGroup).where(HomeGroup.id.in_(group_ids)))}
    return [
        MoveRequestOut(
            id=r.id,
            person=IdName(id=r.person_id, name=people[r.person_id].full_name or ""),
            from_group=IdName(id=r.from_group_id, name=groups[r.from_group_id].name),
            to_group=IdName(id=r.to_group_id, name=groups[r.to_group_id].name),
            agreed=MoveAgreements(
                person=r.agreed_by_person_at is not None,
                from_leader=r.agreed_by_from_leader_at is not None,
                to_leader=r.agreed_by_to_leader_at is not None,
            ),
            state=_state(r),
            created_at=r.created_at,
        )
        for r in requests
    ]


def view(db: Session, request: MoveRequest) -> MoveRequestOut:
    return _view(db, [request])[0]


def listing(
    db: Session, person: Person, *, limit: int, offset: int
) -> tuple[list[MoveRequestOut], int]:
    """The moves that concern the person, as the member or as the leader of either group,
    newest first. One page and the total."""
    led = select(HomeGroup.id).where(HomeGroup.leader_id == person.id)
    query = select(MoveRequest).where(
        or_(
            MoveRequest.person_id == person.id,
            MoveRequest.from_group_id.in_(led),
            MoveRequest.to_group_id.in_(led),
        )
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(MoveRequest.created_at.desc(), MoveRequest.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return (_view(db, rows) if rows else []), total
