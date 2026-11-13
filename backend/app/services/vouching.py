"""Vouch links and vouches (docs/verification.md, "Vouching").

An applicant (PENDING, or a SEARCHER who applies to provide) shares a link with people who know
them. An admitted person who opens it can vouch. Link tokens are long, random and stored hashed,
so a link is shown once when it is made. Every failure to resolve a link is the same `404`.
"""

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_token, new_opaque_token
from app.models.church import Church, HomeGroup, Person
from app.models.trust import Notification, Vouch, VouchLink
from app.schemas.vouching import (
    VouchGiven,
    VouchLinkInfo,
    VouchReceived,
)
from app.services.permissions import can_vouch, live_vouches

VOUCH_RECEIVED = "vouch_received"  # notification kind: someone vouched for you

DAY = timedelta(days=1)


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "This link is not valid")


def seeks_vouches(person: Person) -> bool:
    """Whether the person is an applicant: PENDING, or a SEARCHER who applies to provide."""
    if person.closed_at is not None:
        return False
    return person.status == "pending" or (
        person.status == "searcher" and person.requested_status == "provider"
    )


def _require_applicant(person: Person) -> None:
    if not seeks_vouches(person):
        raise ApiError(409, "not_applying", "You are not asking to be vouched for")


def _active(person_id: uuid.UUID, now: datetime) -> ColumnElement[bool]:
    return and_(
        VouchLink.person_id == person_id,
        VouchLink.revoked_at.is_(None),
        VouchLink.expires_at > now,
    )


def active_link(db: Session, person: Person) -> VouchLink | None:
    _require_applicant(person)
    return db.scalar(
        select(VouchLink)
        .where(_active(person.id, datetime.now(UTC)))
        .order_by(VouchLink.created_at.desc())
        .limit(1)
    )


def create_link(db: Session, settings: Settings, person: Person) -> tuple[VouchLink, str]:
    """A new link; the one before it stops working. The token is returned once."""
    # Lock the row so a leader admitting the person at the same moment is seen here.
    db.refresh(person, with_for_update=True)
    _require_applicant(person)
    now = datetime.now(UTC)
    db.execute(
        update(VouchLink)
        .where(_active(person.id, now))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    token = new_opaque_token()
    link = VouchLink(
        person_id=person.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.vouch_link_days),
    )
    db.add(link)
    db.commit()
    return link, token


def _resolve(db: Session, token: str) -> Person | None:
    """The applicant a link leads to, or None for every kind of failure alike: no such link,
    expired, revoked, or the person no longer asks for vouches."""
    link = db.scalar(select(VouchLink).where(VouchLink.token_hash == hash_token(token)))
    if link is None or link.revoked_at is not None or link.expires_at <= datetime.now(UTC):
        return None
    applicant = db.get(Person, link.person_id)
    if applicant is None or not seeks_vouches(applicant):
        return None
    return applicant


def _check_may_vouch(voucher: Person, applicant: Person) -> None:
    if voucher.id == applicant.id:
        raise ApiError(403, "cannot_vouch_self", "You cannot vouch for yourself")
    if not can_vouch(voucher, applicant):
        raise _not_found()


def _existing(db: Session, voucher_id: uuid.UUID, applicant_id: uuid.UUID) -> Vouch | None:
    return db.scalar(
        select(Vouch).where(Vouch.voucher_id == voucher_id, Vouch.applicant_id == applicant_id)
    )


def link_info(db: Session, voucher: Person, token: str) -> VouchLinkInfo:
    applicant = _resolve(db, token)
    if applicant is None:
        raise _not_found()
    _check_may_vouch(voucher, applicant)
    church = db.get(Church, applicant.church_id)
    group = db.get(HomeGroup, applicant.home_group_id) if applicant.home_group_id else None
    if (
        church is None
        or group is None
        or applicant.requested_status not in ("searcher", "provider")
    ):
        raise _not_found()
    existing = _existing(db, voucher.id, applicant.id)
    return VouchLinkInfo(
        applicant_name=applicant.full_name or "",
        church_name=church.name,
        home_group_name=group.name,
        requested_status=applicant.requested_status,
        already_vouched=existing is not None and existing.withdrawn_at is None,
    )


def _enforce_daily_limit(db: Session, settings: Settings, voucher: Person) -> None:
    cutoff = datetime.now(UTC) - DAY
    created = list(
        db.scalars(
            select(Vouch.created_at)
            .where(Vouch.voucher_id == voucher.id, Vouch.created_at > cutoff)
            .order_by(Vouch.created_at)
        )
    )
    if len(created) >= settings.vouch_max_per_day:
        oldest = created[len(created) - settings.vouch_max_per_day]
        wait = math.ceil((oldest + DAY - datetime.now(UTC)).total_seconds())
        raise ApiError(
            429,
            "rate_limited",
            "You have vouched many times today. Try again later.",
            headers={"Retry-After": str(max(wait, 1))},
        )


def vouch(db: Session, settings: Settings, voucher: Person, token: str) -> Vouch:
    """Vouch for the applicant the link leads to. A vouch that was withdrawn can be given again."""
    applicant = _resolve(db, token)
    if applicant is None:
        raise _not_found()
    # Lock both people, in id order so two people vouching for each other cannot deadlock. The
    # applicant's lock serialises with a leader admitting at the same moment; the voucher's makes
    # parallel requests count one after the other, so the daily limit holds.
    db.scalars(
        select(Person)
        .where(Person.id.in_([voucher.id, applicant.id]))
        .order_by(Person.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    applicant = _resolve(db, token)  # again, now that the rows cannot change under us
    if applicant is None:
        raise _not_found()
    _check_may_vouch(voucher, applicant)
    existing = _existing(db, voucher.id, applicant.id)
    if existing is not None and existing.withdrawn_at is None:
        raise ApiError(409, "already_vouched", "You have already vouched for this person")
    _enforce_daily_limit(db, settings, voucher)
    if existing is not None:
        existing.withdrawn_at = None
        existing.created_at = datetime.now(UTC)
        result = existing
    else:
        result = Vouch(applicant_id=applicant.id, voucher_id=voucher.id)
        db.add(result)
    db.add(Notification(person_id=applicant.id, kind=VOUCH_RECEIVED, subject_id=voucher.id))
    try:
        db.commit()
    except IntegrityError:
        # Two taps at once hit the unique key; anything else is the database refusing a state that
        # changed since the check above.
        db.rollback()
        again = _existing(db, voucher.id, applicant.id)
        if again is not None and again.withdrawn_at is None:
            raise ApiError(
                409, "already_vouched", "You have already vouched for this person"
            ) from None
        raise _not_found() from None
    return result


def withdraw(db: Session, voucher: Person, vouch_id: uuid.UUID) -> None:
    """Take back a vouch, until the applicant is admitted. Withdrawing twice is not an error."""
    found = db.get(Vouch, vouch_id)
    if found is None or found.voucher_id != voucher.id:
        raise ApiError(404, "not_found", "There is no such vouch")
    applicant = db.get(Person, found.applicant_id, with_for_update=True)
    if applicant is None:
        raise ApiError(404, "not_found", "There is no such vouch")
    if found.withdrawn_at is not None:
        return
    if not seeks_vouches(applicant):
        raise ApiError(409, "not_pending", "This person has been admitted or has left")
    found.withdrawn_at = datetime.now(UTC)
    db.commit()


# The lists show the newest vouches; the number of vouches a person gives or receives is small.
MAX_LISTED = 200


def received(db: Session, person: Person) -> list[VouchReceived]:
    rows = list(
        db.scalars(
            select(Vouch)
            .where(Vouch.applicant_id == person.id)
            .order_by(Vouch.created_at.desc(), Vouch.id)
            .limit(MAX_LISTED)
        )
    )
    if not rows:
        return []
    vouchers = {
        p.id: p
        for p in db.scalars(select(Person).where(Person.id.in_([v.voucher_id for v in rows])))
    }
    live = set(live_vouches([(v.voucher_id, v.withdrawn_at) for v in rows], vouchers))
    churches = {
        c.id: c.name
        for c in db.scalars(
            select(Church).where(Church.id.in_({p.church_id for p in vouchers.values()}))
        )
    }
    return [
        VouchReceived(
            id=v.id,
            voucher_name=vouchers[v.voucher_id].full_name or "",
            church_name=churches.get(vouchers[v.voucher_id].church_id, ""),
            live=v.voucher_id in live,
            created_at=v.created_at,
        )
        for v in rows
    ]


def given(db: Session, person: Person) -> list[VouchGiven]:
    rows = db.execute(
        select(Vouch, Person)
        .join(Person, Person.id == Vouch.applicant_id)
        .where(Vouch.voucher_id == person.id)
        .order_by(Vouch.created_at.desc(), Vouch.id)
        .limit(MAX_LISTED)
    ).all()
    return [
        VouchGiven(
            id=v.id,
            applicant_name=a.full_name or "",
            applicant_status=a.status,
            requested_status=a.requested_status,
            withdrawn=v.withdrawn_at is not None,
            can_withdraw=v.withdrawn_at is None and seeks_vouches(a),
            created_at=v.created_at,
        )
        for v, a in rows
    ]
