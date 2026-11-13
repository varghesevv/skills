"""Reading a person's status history."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.church import Person
from app.models.trust import StatusChange
from app.services.permissions import LastChange


def last_change(db: Session, person: Person) -> LastChange | None:
    """The person's latest status change and the current status of whoever made it."""
    row = db.execute(
        select(StatusChange, Person.status)
        .outerjoin(Person, Person.id == StatusChange.changed_by_id)
        .where(StatusChange.person_id == person.id)
        .order_by(StatusChange.at.desc(), StatusChange.id)
        .limit(1)
    ).first()
    if row is None:
        return None
    change, changer_status = row
    return LastChange(kind=change.kind, changed_by_status=changer_status)
