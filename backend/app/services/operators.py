"""What the platform operators do directly on the database, outside the app.

Today: set up Skills by creating the first OWNER with the first church and home group. The
operator change of the OWNER (docs/verification.md, "Owner succession") shares its logic with the
handover and arrives with it (roadmap S4.5).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.church import Church, HomeGroup, Person
from app.models.trust import StatusChange


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
