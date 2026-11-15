"""Row locks on people, taken in one fixed order so two requests cannot deadlock.

The order of locks across the app: people first (by id), then home groups, then churches. Code
that locks a group (closing it, placing someone in it) takes the people it acts on before it.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Person
from app.services.permissions import in_scope, is_verifier


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


def locked_in_scope(
    db: Session, actor: Person, person_id: uuid.UUID, also: Iterable[uuid.UUID] = ()
) -> Person:
    """Lock the actor and the person, and return the person if the actor may act on them.

    A person who does not exist, is closed, is the actor or is out of the actor's scope is the
    same `404`, so nothing says whether they exist. An actor who stopped being a leader while the
    request was on its way is refused.

    `also` are other people the operation will change (a successor): they are locked in the same
    ordered call, so two operations cannot lock them in opposite orders.
    """
    locked = lock_people(db, [actor.id, person_id, *also])
    person = locked.get(person_id)
    if (
        person is None
        or person.closed_at is not None
        or person.id == actor.id
        or not in_scope(actor, person)
    ):
        raise ApiError(404, "not_found", "There is no such person")
    if not is_verifier(actor):
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    return person
