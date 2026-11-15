"""The log of phone number views (docs/verification.md, decision O-03).

Each time a leader's screen shows a person's number, a row records who looked at whom and when,
never the number. The OWNER reads the log; rows older than the retention are deleted by a command.
"""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import ContactView, Person
from app.schemas.church import IdName
from app.schemas.contact_views import ContactViewOut


def listing(
    db: Session,
    *,
    limit: int,
    offset: int,
    viewer_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
) -> tuple[list[ContactViewOut], int]:
    """The views, newest first, optionally of one viewer or person. One page and the total."""
    query = select(ContactView)
    if viewer_id is not None:
        query = query.where(ContactView.viewer_id == viewer_id)
    if person_id is not None:
        query = query.where(ContactView.person_id == person_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(ContactView.viewed_at.desc(), ContactView.id).limit(limit).offset(offset)
        )
    )
    # A closed account has no name any more: the row keeps who it was, the name is empty.
    ids = {r.viewer_id for r in rows} | {r.person_id for r in rows}
    names = (
        {p.id: p.full_name or "" for p in db.scalars(select(Person).where(Person.id.in_(ids)))}
        if ids
        else {}
    )
    return (
        [
            ContactViewOut(
                id=r.id,
                viewer=IdName(id=r.viewer_id, name=names.get(r.viewer_id, "")),
                person=IdName(id=r.person_id, name=names.get(r.person_id, "")),
                screen=r.screen,
                viewed_at=r.viewed_at,
            )
            for r in rows
        ],
        total,
    )


def purge_older_than(db: Session, cutoff: datetime) -> int:
    """Delete the views before `cutoff` (the retention of O-03). Returns how many."""
    result = db.execute(delete(ContactView).where(ContactView.viewed_at < cutoff))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
