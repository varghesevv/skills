"""A planned handover of the OWNER role: the OWNER proposes, the chosen ADMIN accepts.

Everything happens, in one transaction, when the chosen ADMIN accepts (`ownership.transfer`). What
was true when the OWNER proposed is checked again then: people and churches may have changed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.trust import HandoverRequest, Notification
from app.schemas.church import IdName
from app.schemas.handover import HandoverAccepted, HandoverOut
from app.services import ownership
from app.services.locks import lock_people

HANDOVER_REQUESTED = (
    "handover_requested"  # notification kind: the OWNER proposes to hand over to you
)
HANDOVER_CANCELLED = "handover_cancelled"  # notification kind: the handover was cancelled


def _open(request: HandoverRequest) -> bool:
    return request.accepted_at is None and request.cancelled_at is None


def _person(db: Session, person_id: uuid.UUID) -> IdName:
    person = db.get(Person, person_id)
    return IdName(id=person_id, name=(person.full_name if person else "") or "")


def _name(db: Session, person_id: uuid.UUID | None) -> IdName | None:
    return _person(db, person_id) if person_id is not None else None


def view(db: Session, request: HandoverRequest) -> HandoverOut:
    return HandoverOut(
        id=request.id,
        owner=_person(db, request.owner_id),
        new_owner=_person(db, request.new_owner_id),
        successor_admin=_name(db, request.successor_admin_id),
        successor_leader=_name(db, request.successor_leader_id),
        former_owner_status=request.former_owner_status,
        created_at=request.created_at,
    )


def current(db: Session, person: Person) -> HandoverRequest | None:
    return db.scalar(
        select(HandoverRequest).where(
            HandoverRequest.accepted_at.is_(None),
            HandoverRequest.cancelled_at.is_(None),
            (HandoverRequest.owner_id == person.id) | (HandoverRequest.new_owner_id == person.id),
        )
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        diag = getattr(error.orig, "diag", None)
        if getattr(diag, "constraint_name", None) == "uq_handover_requests_one_open":
            raise ApiError(409, "handover_open", "A handover is already proposed") from None
        raise ApiError(
            409, "state_changed", "Something changed meanwhile. Reload and try again."
        ) from None


def propose(
    db: Session,
    owner: Person,
    new_owner_id: uuid.UUID,
    successor_admin_id: uuid.UUID | None,
    successor_leader_id: uuid.UUID | None,
    former_owner_status: str,
) -> HandoverRequest:
    wanted = [i for i in (new_owner_id, successor_admin_id, successor_leader_id) if i is not None]
    people = lock_people(db, [owner.id, *wanted])
    me = people.get(owner.id)
    if me is None or me.closed_at is not None or me.status != "owner":
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    new = people.get(new_owner_id)
    church_new = db.get(Church, new.church_id) if new is not None else None
    if (
        new is None
        or new.closed_at is not None
        or new.status != "admin"
        or new.church_id == me.church_id
        or church_new is None
        or church_new.closed_at is not None
        or church_new.admin_id != new.id
    ):
        raise ApiError(422, "invalid_choice", "Choose the ADMIN of another church to hand over to")
    church = db.get(Church, me.church_id)
    group = db.get(HomeGroup, me.home_group_id) if me.home_group_id else None
    if church is None:
        raise ApiError(409, "state_changed", "Something changed meanwhile. Reload.")
    ownership.check_admin_successor(db, church, me, successor_admin_id)
    ownership.check_leader_successor(db, group, me, successor_leader_id)
    request = HandoverRequest(
        owner_id=me.id,
        new_owner_id=new.id,
        successor_admin_id=successor_admin_id,
        successor_leader_id=successor_leader_id,
        former_owner_status=former_owner_status,
    )
    db.add(request)
    db.add(Notification(person_id=new.id, kind=HANDOVER_REQUESTED, subject_id=me.id))
    _commit(db)
    return request


def accept(db: Session, actor: Person, request_id: uuid.UUID) -> HandoverRequest:
    found = db.get(HandoverRequest, request_id)
    if found is None or found.new_owner_id != actor.id:
        raise ApiError(404, "not_found", "There is no such handover")
    wanted = [i for i in (found.successor_admin_id, found.successor_leader_id) if i is not None]
    people = lock_people(db, [found.owner_id, actor.id, *wanted])
    request = db.get(HandoverRequest, request_id, with_for_update=True, populate_existing=True)
    old, new = people.get(found.owner_id), people.get(actor.id)
    if request is None or old is None or new is None:
        raise ApiError(404, "not_found", "There is no such handover")
    if not _open(request):
        raise ApiError(409, "not_open", "This handover has been decided")
    if old.status != "owner" or old.closed_at is not None or new.status != "admin":
        raise ApiError(
            409,
            "request_stale",
            "The OWNER or the chosen ADMIN is not what they were; propose again",
        )
    ownership.transfer(
        db,
        old=old,
        new=new,
        admin_successor_id=request.successor_admin_id,
        leader_successor_id=request.successor_leader_id,
        former_status=request.former_owner_status,
        kind="handover",
    )
    request.accepted_at = datetime.now(UTC)
    _commit(db)
    return request


def cancel(db: Session, actor: Person, request_id: uuid.UUID) -> HandoverRequest:
    found = db.get(HandoverRequest, request_id)
    if found is None or actor.id not in (found.owner_id, found.new_owner_id):
        raise ApiError(404, "not_found", "There is no such handover")
    lock_people(db, [found.owner_id, found.new_owner_id])
    request = db.get(HandoverRequest, request_id, with_for_update=True, populate_existing=True)
    if request is None:
        raise ApiError(404, "not_found", "There is no such handover")
    if not _open(request):
        raise ApiError(409, "not_open", "This handover has been decided")
    request.cancelled_at = datetime.now(UTC)
    other = request.new_owner_id if actor.id == request.owner_id else request.owner_id
    db.add(Notification(person_id=other, kind=HANDOVER_CANCELLED, subject_id=actor.id))
    _commit(db)
    return request


def accepted_view(db: Session, request: HandoverRequest) -> HandoverAccepted:
    """What an acceptance answers: the new OWNER, and what the outgoing one is now."""
    former = db.get(Person, request.owner_id)
    return HandoverAccepted(
        owner=_person(db, request.new_owner_id),
        former_owner=_person(db, request.owner_id),
        former_owner_status=former.status if former else "",
    )
