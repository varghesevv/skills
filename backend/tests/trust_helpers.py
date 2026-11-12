"""Builders for tests of the church trust schema.

Most rules of the model hold only at COMMIT (deferred constraints). Tests run inside a
transaction that is rolled back, so `check_rules` asks PostgreSQL to check them now.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Church, HomeGroup, Person

# Not a credential: a placeholder for the hash column, which the tests never check.
FAKE_HASH = "placeholder-hash"

_counter = iter(range(1, 10_000_000))


def check_rules(session: Session) -> None:
    """Run the deferred rules now. Raises IntegrityError when one is broken."""
    session.flush()
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    session.execute(text("SET CONSTRAINTS ALL DEFERRED"))


def make_person(
    church: Church | None,
    group: HomeGroup | None,
    status: str,
    *,
    person_id: uuid.UUID | None = None,
    church_id: uuid.UUID | None = None,
    **extra: object,
) -> Person:
    n = next(_counter)
    values: dict[str, object] = {
        "id": person_id or uuid.uuid4(),
        "status": status,
        "church_id": church_id or (church.id if church else None),
        "home_group_id": None if status == "revoked" else (group.id if group else None),
        "full_name": f"Person {n}",
        "email": f"person{n}@example.com",
        "mobile_number": f"+97150{n:07d}",
        "password_hash": FAKE_HASH,
    }
    values.update(extra)
    return Person(**values)


class World:
    """An OWNER who is the ADMIN of the first church and the leader of its first home group."""

    def __init__(self, session: Session) -> None:
        self.session = session
        owner_id = uuid.uuid4()
        self.church = Church(id=uuid.uuid4(), name="First church", admin_id=owner_id)
        session.add(self.church)
        session.flush()
        self.group = HomeGroup(
            id=uuid.uuid4(), church_id=self.church.id, name="First group", leader_id=owner_id
        )
        session.add(self.group)
        session.flush()
        self.owner = make_person(self.church, self.group, "owner", person_id=owner_id)
        session.add(self.owner)
        check_rules(session)

    def add_person(self, status: str, group: HomeGroup | None = None, **extra: object) -> Person:
        person = make_person(self.church, group or self.group, status, **extra)
        self.session.add(person)
        self.session.flush()
        return person

    def add_church(self, name: str = "Second church") -> tuple[Church, HomeGroup, Person]:
        """A second church, created the way an accepted invitation does: ADMIN and leader."""
        admin_id = uuid.uuid4()
        church = Church(id=uuid.uuid4(), name=name, admin_id=admin_id)
        self.session.add(church)
        self.session.flush()
        group = HomeGroup(
            id=uuid.uuid4(), church_id=church.id, name=f"{name} group", leader_id=admin_id
        )
        self.session.add(group)
        self.session.flush()
        admin = make_person(church, group, "admin", person_id=admin_id)
        self.session.add(admin)
        check_rules(self.session)
        return church, group, admin

    def add_group(self, leader: Person, name: str = "Another group") -> HomeGroup:
        """A new group in the first church; the leader moves into it (one transaction)."""
        group = HomeGroup(id=uuid.uuid4(), church_id=self.church.id, name=name, leader_id=leader.id)
        self.session.add(group)
        self.session.flush()
        leader.home_group_id = group.id
        if leader.status in ("pending", "searcher", "provider"):
            leader.status = "verifier"  # a new leader becomes a VERIFIER unless higher
        self.session.flush()
        return group


def now() -> datetime:
    return datetime.now(UTC)
