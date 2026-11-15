"""A searcher who wants to become a provider (docs/verification.md, "Joining", step 12).

They need the same vouches as a new provider applicant, get a vouch link in the same way, and
keep searching while they collect vouches. Their home group's leader admits them as a provider,
or declines the request, which ends the request and leaves them a searcher.
"""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import HomeGroup, Person
from app.models.trust import Notification, VouchLink

PROVIDER_APPLICATION = "provider_application"  # notification kind: a searcher of yours applies
PROVIDER_DECLINED = "provider_declined"  # notification kind: your leader declined your request


def apply_for_provider(db: Session, person: Person) -> None:
    """Ask to become a provider. Asking again changes nothing and notifies nobody."""
    # Hold the row: a leader acting on this person at the same moment waits for us.
    db.refresh(person, with_for_update=True)
    if person.closed_at is not None or person.status != "searcher":
        db.rollback()
        raise ApiError(409, "not_searcher", "Only a searcher can apply to become a provider")
    if person.requested_status == "provider":
        db.rollback()
        return
    person.requested_status = "provider"
    group = db.get(HomeGroup, person.home_group_id) if person.home_group_id else None
    if group is not None and group.closed_at is None:
        db.add(
            Notification(person_id=group.leader_id, kind=PROVIDER_APPLICATION, subject_id=person.id)
        )
    db.commit()


def end_request(db: Session, person: Person, decided_by: Person) -> None:
    """The leader declines the request: the person stays a searcher, the link stops working and
    the vouches stay on record. The caller commits."""
    person.requested_status = None
    db.execute(
        update(VouchLink)
        .where(VouchLink.person_id == person.id, VouchLink.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    db.add(Notification(person_id=person.id, kind=PROVIDER_DECLINED, subject_id=decided_by.id))
