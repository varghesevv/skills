"""Revoking, reinstating and re-confirming people (docs/verification.md, "Revocation").

A leader revokes a person in their scope who is below them; the person leaves their home group
(the group stays on record) and is kept on the church's revoked list. A leader at the level of the
one who revoked them, or higher, reinstates them into a home group. Everyone whose status a revoked
leader set is flagged for re-checking and keeps their access, until a leader at that leader's level
or higher re-confirms them.

Each operation changes the status, who set it, the history and the notification in one
transaction, under row locks on the leader and the person.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK
from app.models.trust import Notification, StatusChange, VouchLink
from app.services import succession
from app.services.locks import locked_in_scope
from app.services.permissions import can_reconfirm, can_set_status, in_scope, rank
from app.services.status_history import last_change

REVOKED = "revoked"  # notification kind: a leader revoked you
REINSTATED = "reinstated"  # notification kind: a leader reinstated you


def _not_allowed() -> ApiError:
    return ApiError(403, "status_not_allowed", "You may not make this change")


def _history(
    person: Person, previous: str, actor: Person, kind: str, *, to: str | None = None
) -> StatusChange:
    # The time is set here, not by the database, so changes made in one transaction still have an
    # order ("the latest change" is read by time).
    return StatusChange(
        person_id=person.id,
        from_status=previous,
        to_status=to or person.status,
        changed_by_id=actor.id,
        kind=kind,
        at=datetime.now(UTC),
    )


def flag_people_set_by(db: Session, revoked: Person) -> int:
    """Flag everyone whose current status `revoked` set. Their statuses do not change and they
    keep their access. Returns how many were newly flagged."""
    result = db.execute(
        update(Person)
        .where(
            Person.status_set_by_id == revoked.id,
            Person.closed_at.is_(None),
            Person.status != REVOKED,
            Person.id != revoked.id,
            Person.flagged_for_recheck.is_(False),  # already flagged: not counted again
        )
        .values(flagged_for_recheck=True)
        .execution_options(synchronize_session=False)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def revoke(
    db: Session,
    actor: Person,
    person_id: uuid.UUID,
    successor_id: uuid.UUID | None = None,
    group_successor_id: uuid.UUID | None = None,
) -> Person:
    """Revoke a person in scope.

    A VERIFIER's group gets a successor (`successor_id`) in the same step, or closes when the
    VERIFIER is its only member. A church's ADMIN is replaced by `successor_id` (a member of the
    church) and the group they lead passes to `group_successor_id` or closes when they are alone
    in it. Everyone whose status a revoked leader set is flagged.
    """
    also = [i for i in (successor_id, group_successor_id) if i is not None]
    person = locked_in_scope(db, actor, person_id, also=also)
    if person.status == REVOKED:
        raise ApiError(409, "already_revoked", "This person is already revoked")
    if not can_set_status(actor, person, REVOKED, last_change(db, person)):
        raise _not_allowed()
    if (successor_id is not None and person.status not in ("verifier", "admin")) or (
        group_successor_id is not None and person.status != "admin"
    ):
        raise ApiError(422, "invalid_choice", "Only a leader has a successor")
    previous = person.status
    if previous == "admin":
        church = db.get(Church, person.church_id)
        if church is None or successor_id is None:
            raise ApiError(
                409,
                "successor_required",
                "An ADMIN is replaced first: choose a member of the church",
            )
        succession.hand_church_on(
            db, church, person, actor, successor_id, group_successor_id, revoking=True
        )
        flag_people_set_by(db, person)
    elif previous == "verifier":
        group = db.get(HomeGroup, person.home_group_id, with_for_update=True)
        if group is None:  # cannot happen: a VERIFIER always leads their own group
            raise ApiError(409, "state_changed", "This person changed meanwhile. Reload.")
        succession.end_leadership(db, group, person, actor, successor_id)
        flag_people_set_by(db, person)
    person.last_home_group_id = person.home_group_id
    person.home_group_id = None
    person.status = REVOKED
    person.status_set_by_id = actor.id
    person.requested_status = None
    person.flagged_for_recheck = False
    # Their link stops working, and their vouches stop counting (that follows from the status).
    db.execute(
        update(VouchLink)
        .where(VouchLink.person_id == person.id, VouchLink.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    db.add(_history(person, previous, actor, "revoke"))
    db.add(Notification(person_id=person.id, kind=REVOKED, subject_id=actor.id))
    _commit(db)
    return person


def reinstate(
    db: Session, actor: Person, person_id: uuid.UUID, to: str, home_group_id: uuid.UUID
) -> Person:
    person = locked_in_scope(db, actor, person_id)
    if person.status != REVOKED:
        raise ApiError(409, "not_revoked", "This person is not revoked")
    if not can_set_status(actor, person, to, last_change(db, person)):
        raise _not_allowed()
    # Locked after the people (the order of locks in services/locks.py), so a group that closes at
    # this moment waits for us, or we see it closed.
    group = db.get(HomeGroup, home_group_id, with_for_update=True)
    church = db.get(Church, group.church_id) if group else None
    if (
        group is None
        or group.closed_at is not None
        or church is None
        or church.closed_at is not None
        or group.church_id != person.church_id
    ):
        raise ApiError(422, "invalid_choice", "That home group is not available")
    # The leader may place them only where they have authority: their own group (a church's ADMIN
    # and the OWNER, any group of the church).
    placed = Person(
        id=person.id,
        status=to,
        church_id=person.church_id,
        home_group_id=group.id,
        last_home_group_id=None,
        closed_at=None,
    )
    if not in_scope(actor, placed):
        raise _not_allowed()
    person.status = to
    person.home_group_id = group.id
    person.last_home_group_id = None
    person.status_set_by_id = actor.id
    db.add(_history(person, REVOKED, actor, "reinstate", to=to))
    db.add(Notification(person_id=person.id, kind=REINSTATED, subject_id=actor.id))
    _commit(db)
    return person


def _level_of_revoked_setter(db: Session, person: Person) -> int:
    """The rank the leader who set this person's status had when they were revoked. If it cannot
    be known (no such revocation), a VERIFIER's, the lowest leader level."""
    if person.status_set_by_id is None:
        return rank("verifier")
    previous = db.scalar(
        select(StatusChange.from_status)
        .where(
            StatusChange.person_id == person.status_set_by_id,
            StatusChange.to_status == REVOKED,
        )
        .order_by(StatusChange.at.desc(), StatusChange.id)
        .limit(1)
    )
    return STATUS_RANK.get(previous or "", rank("verifier"))


def reconfirm(db: Session, actor: Person, person_id: uuid.UUID) -> Person:
    """Clear the re-check flag: the leader now vouches for this person, and becomes the new link
    in their chain of trust."""
    person = locked_in_scope(db, actor, person_id)
    if not person.flagged_for_recheck:
        raise ApiError(409, "not_flagged", "This person is not flagged for re-checking")
    if not can_reconfirm(actor, person, _level_of_revoked_setter(db, person)):
        raise _not_allowed()
    person.flagged_for_recheck = False
    person.status_set_by_id = actor.id
    db.add(_history(person, person.status, actor, "reconfirm"))
    _commit(db)
    return person


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # The database refuses a state the checks above did not foresee; nothing is half done.
        db.rollback()
        raise ApiError(
            409, "state_changed", "This person changed meanwhile. Reload and retry."
        ) from None
