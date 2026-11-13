"""Row locks on people, taken in one fixed order so two requests cannot deadlock."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.church import Person


def lock_people(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Person]:
    """Lock the people (in id order) and refresh them, so what the caller checks next is what
    is in the database. People who do not exist are left out."""
    rows = db.scalars(
        select(Person)
        .where(Person.id.in_(set(ids)))
        .order_by(Person.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {p.id: p for p in rows}
