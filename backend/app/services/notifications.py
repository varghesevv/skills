"""In-app notifications (decisions D-09, D-18, O-02).

A notification is a row written in the same transaction as the event it reports, by the service
that handles the event. It holds only the kind and the id of the person it is about; the name is
loaded when the list is read, so a closed account shows no name. Clients poll the list.
"""

import calendar
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Person
from app.models.trust import Notification
from app.schemas.church import IdName
from app.schemas.notifications import NotificationItem, NotificationList
from app.services.admission import ADMITTED
from app.services.signup import NEW_APPLICANT
from app.services.vouching import VOUCH_RECEIVED

# The events the model names (FR-C-12) that exist so far. Later slices add their kinds here:
# revoked and re-check flag (4.1), requests to agree to a move or a handover (4.4, 4.5).
KINDS = (NEW_APPLICANT, VOUCH_RECEIVED, ADMITTED)


def listing(
    db: Session, person: Person, *, limit: int, offset: int, unread_only: bool
) -> NotificationList:
    mine = Notification.person_id == person.id
    unread = Notification.read_at.is_(None)
    query = select(Notification).where(mine)
    if unread_only:
        query = query.where(unread)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    unread_count = (
        db.scalar(select(func.count()).select_from(Notification).where(mine, unread)) or 0
    )
    rows = list(
        db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id)
            .limit(limit)
            .offset(offset)
        )
    )
    subject_ids = {n.subject_id for n in rows if n.subject_id}
    subjects = (
        {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(subject_ids)))}
        if subject_ids
        else {}
    )
    return NotificationList(
        total=total,
        unread_count=unread_count,
        items=[
            NotificationItem(
                id=n.id,
                kind=n.kind,
                subject=_subject(subjects.get(n.subject_id)) if n.subject_id else None,
                created_at=n.created_at,
                read=n.read_at is not None,
            )
            for n in rows
        ],
    )


def _subject(person: Person | None) -> IdName | None:
    # A closed account has no name left; the id stays so the client can tell it is gone.
    return IdName(id=person.id, name=person.full_name or "") if person else None


def mark_read(db: Session, person: Person, notification_id: uuid.UUID) -> None:
    """Mark one as read. Someone else's, or none, is the same `404`; reading twice is fine."""
    found = db.get(Notification, notification_id)
    if found is None or found.person_id != person.id:
        raise ApiError(404, "not_found", "There is no such notification")
    if found.read_at is None:
        found.read_at = func.now()
        db.commit()


def mark_all_read(db: Session, person: Person) -> None:
    db.execute(
        update(Notification)
        .where(Notification.person_id == person.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    db.commit()


def months_before(moment: datetime, months: int) -> datetime:
    """The same day `months` calendar months earlier (the last day of the month if it has no
    such day, so 31 March minus one month is 28 or 29 February)."""
    index = moment.year * 12 + (moment.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return moment.replace(year=year, month=month, day=min(moment.day, last_day))


def purge_older_than(db: Session, cutoff: datetime) -> int:
    """Delete notifications created before `cutoff` (the retention of O-02). Returns how many."""
    result = db.execute(delete(Notification).where(Notification.created_at < cutoff))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
