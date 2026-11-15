"""Admitting and declining applicants (docs/verification.md, "Joining").

A leader (VERIFIER) acts on applicants of their own home group, an ADMIN on those of their church,
the OWNER on anyone's. A person out of scope, or who does not exist, is the same `404`. The checks
are the permission functions; this module loads what they need, takes the row locks, and changes
everything in one transaction: the status, who set it, the history row and the notification.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Person
from app.models.trust import Notification, StatusChange, VouchLink
from app.services import account_closing, provider_upgrade, vouching
from app.services.locks import locked_in_scope
from app.services.permissions import (
    can_admit,
    can_decline,
    can_decline_upgrade,
)

ADMITTED = "admitted"  # notification kind: a leader admitted you


def admit(db: Session, actor: Person, person_id: uuid.UUID, to: str) -> Person:
    applicant = locked_in_scope(db, actor, person_id)
    waiting_for_provider = (
        applicant.status == "searcher" and applicant.requested_status == "provider"
    )
    if not (applicant.status == "pending" or (to == "provider" and waiting_for_provider)):
        raise ApiError(409, "not_pending", "This person is not waiting to be admitted")
    if not can_admit(actor, applicant, to, vouching.live_voucher_ids(db, applicant)):
        raise ApiError(
            409, "not_enough_vouches", "A provider needs a vouch from someone besides you"
        )
    previous = applicant.status
    applicant.status = to
    applicant.status_set_by_id = actor.id
    # Admitted as a searcher while applying to provide: the person goes on collecting vouches.
    if not (to == "searcher" and applicant.requested_status == "provider"):
        applicant.requested_status = None
        db.execute(
            update(VouchLink)
            .where(VouchLink.person_id == applicant.id, VouchLink.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    db.add(
        StatusChange(
            person_id=applicant.id,
            from_status=previous,
            to_status=to,
            changed_by_id=actor.id,
            kind="admit",
        )
    )
    db.add(Notification(person_id=applicant.id, kind=ADMITTED, subject_id=actor.id))
    _commit(db)
    return applicant


def decline(db: Session, actor: Person, person_id: uuid.UUID) -> None:
    """Close an application. Nobody is revoked; the person can sign up again later. For a searcher
    who asked to become a provider, only the request ends."""
    applicant = locked_in_scope(db, actor, person_id)
    if can_decline_upgrade(actor, applicant):
        # A searcher who asked to become a provider: the request ends, the account stays.
        provider_upgrade.end_request(db, applicant, actor)
        _commit(db)
        return
    if not can_decline(actor, applicant):
        raise ApiError(409, "not_pending", "This person is not waiting to be admitted")
    account_closing.clear_account(db, applicant, datetime.now(UTC))
    _commit(db)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # The database refuses a state the checks above did not foresee, such as a change that
        # would break a rule of the model. Nothing is half done.
        db.rollback()
        raise ApiError(
            409, "state_changed", "This person changed meanwhile. Reload and retry."
        ) from None
