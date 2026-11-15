"""What the platform operators do directly on the database, outside the app.

Set up Skills by creating the first OWNER with the first church and home group, and change the
OWNER when they cannot hand over or have breached trust (docs/verification.md, "Owner succession"),
with the same appointments as a handover (`ownership.transfer`) and no person behind them in the
history.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password
from app.models.church import Church, HomeGroup, Person
from app.models.trust import HandoverRequest, StatusChange
from app.services import ownership
from app.services.locks import lock_people


class SetupError(Exception):
    """The setup cannot be done. The message is safe to print: it holds no personal detail."""


@dataclass(frozen=True)
class FirstOwner:
    person_id: uuid.UUID
    church_id: uuid.UUID
    home_group_id: uuid.UUID


_ALREADY_SET_UP = "Skills is already set up: there is an OWNER."


def _owner_exists(db: Session) -> bool:
    return (
        db.scalar(select(Person.id).where(Person.status == "owner", Person.closed_at.is_(None)))
        is not None
    )


def create_first_owner(
    db: Session,
    *,
    full_name: str,
    email: str,
    mobile_number: str,
    password: str,
    church_name: str,
    group_name: str,
) -> FirstOwner:
    """Create the OWNER, their church (they are its ADMIN) and their home group (they lead it).

    All in one transaction, committed here. Refuses when an open OWNER already exists: there is
    always exactly one, and a replacement goes through a handover or an operator change.
    """
    if _owner_exists(db):
        raise SetupError(_ALREADY_SET_UP)
    owner_id, church_id, group_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        # The three rows refer to each other; the references are checked at commit.
        db.add(Church(id=church_id, name=church_name.strip(), admin_id=owner_id))
        db.flush()
        db.add(
            HomeGroup(id=group_id, church_id=church_id, name=group_name.strip(), leader_id=owner_id)
        )
        db.flush()
        db.add(
            Person(
                id=owner_id,
                status="owner",
                church_id=church_id,
                home_group_id=group_id,
                full_name=full_name.strip(),
                email=email.strip().lower(),
                mobile_number=mobile_number,
                password_hash=hash_password(password),
            )
        )
        db.add(
            StatusChange(
                person_id=owner_id,
                from_status=None,
                to_status="owner",
                changed_by_id=None,
                kind="operator",
            )
        )
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        # Two setups at once: the database allows one OWNER, so the other one lost.
        if _owner_exists(db):
            raise SetupError(_ALREADY_SET_UP) from None
        raise SetupError(
            "The OWNER could not be created: check the name lengths and that the email address "
            "and mobile number are not in use."
        ) from None
    return FirstOwner(owner_id, church_id, group_id)


@dataclass(frozen=True)
class OwnerChanged:
    old_owner_id: uuid.UUID
    new_owner_id: uuid.UUID
    old_owner_status: str  # what the old OWNER is now
    flagged: int  # people flagged for re-checking (only when the old OWNER was revoked)


def _open_person(db: Session, email: str, what: str) -> Person:
    person = db.scalar(
        select(Person).where(Person.email == email.strip().lower(), Person.closed_at.is_(None))
    )
    if person is None:
        raise SetupError(f"There is no open account with the address given for {what}.")
    return person


def change_owner(
    db: Session,
    *,
    new_owner_email: str,
    former_status: str = "provider",
    admin_successor_email: str | None = None,
    leader_successor_email: str | None = None,
    revoke_old_owner: bool = False,
) -> OwnerChanged:
    """Make an ADMIN of another church the OWNER, outside the app. Committed here.

    The same appointments as a handover: a new ADMIN for the old OWNER's church and a new leader for
    the group they led (each may be left out only when nobody else is there, and the old OWNER then
    keeps that role). When the old OWNER breached trust (`revoke_old_owner`) they are revoked, and
    everyone whose status they set is flagged; the new OWNER clears the flags. A handover
    proposal still open is cancelled. Everything is one transaction, written to the history as an
    operator change.
    """
    if former_status not in ("provider", "searcher"):
        raise SetupError("The old OWNER becomes a provider or a searcher.")
    old = db.scalar(select(Person).where(Person.status == "owner", Person.closed_at.is_(None)))
    if old is None:
        raise SetupError("There is no OWNER to replace: set Skills up first.")
    new = _open_person(db, new_owner_email, "the new OWNER")
    admin_successor = (
        _open_person(db, admin_successor_email, "the new ADMIN") if admin_successor_email else None
    )
    leader_successor = (
        _open_person(db, leader_successor_email, "the new group leader")
        if leader_successor_email
        else None
    )
    if new.status != "admin" or new.church_id == old.church_id:
        raise SetupError("The new OWNER must be the ADMIN of a church other than the OWNER's.")
    wanted = [p.id for p in (admin_successor, leader_successor) if p is not None]
    try:
        people = lock_people(db, [old.id, new.id, *wanted])
        locked_old, locked_new = people[old.id], people[new.id]
        flagged = ownership.transfer(
            db,
            old=locked_old,
            new=locked_new,
            admin_successor_id=admin_successor.id if admin_successor else None,
            leader_successor_id=leader_successor.id if leader_successor else None,
            former_status=former_status,
            kind="operator",
            revoke_old=revoke_old_owner,
        )
        # A proposal of the old OWNER is for a change that no longer applies.
        db.execute(
            update(HandoverRequest)
            .where(
                HandoverRequest.accepted_at.is_(None),
                HandoverRequest.cancelled_at.is_(None),
                HandoverRequest.owner_id == old.id,
            )
            .values(cancelled_at=datetime.now(UTC))
        )
        db.commit()
    except ApiError as error:
        db.rollback()
        raise SetupError(error.message) from None
    except (IntegrityError, DataError):
        db.rollback()
        raise SetupError(
            "The OWNER could not be changed: the database refused the result (nothing was changed)."
        ) from None
    return OwnerChanged(
        old_owner_id=old.id,
        new_owner_id=new.id,
        old_owner_status=locked_old.status,
        flagged=flagged,
    )
