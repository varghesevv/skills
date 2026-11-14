"""Revealing a provider's mobile number: the limits, the lock and the record of each reveal."""

import math
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.models.church import Person
from app.models.reveals import PersonPhoneReveal
from app.schemas.profiles import RevealRequest
from app.services import locks
from app.services.profiles import utc_now
from app.services.providers import visible_provider


def check_reveal_limits(db: Session, settings: Settings, revealer_id: uuid.UUID) -> None:
    """Answer 429 when this person has asked for too many numbers lately.

    For each window one bounded query fetches only the reveal that is `limit` places back from
    the newest. If it exists, the limit is reached, and the same row says when the window frees
    a place again (Retry-After).
    """
    now = utc_now()
    for window, limit in (
        (timedelta(hours=1), settings.reveal_max_per_hour),
        (timedelta(days=1), settings.reveal_max_per_day),
    ):
        oldest_counted = db.scalar(
            select(PersonPhoneReveal.revealed_at)
            .where(
                PersonPhoneReveal.revealer_id == revealer_id,
                PersonPhoneReveal.revealed_at > now - window,
            )
            .order_by(PersonPhoneReveal.revealed_at.desc())
            .offset(limit - 1)
            .limit(1)
        )
        if oldest_counted is not None:
            wait = math.ceil((oldest_counted + window - now).total_seconds())
            raise ApiError(
                429,
                "reveal_limit_reached",
                "You have revealed too many mobile numbers. Try again later.",
                headers={"Retry-After": str(max(wait, 1))},
            )


def reveal_mobile_number(
    db: Session,
    settings: Settings,
    *,
    revealer: Person,
    provider_id: uuid.UUID,
    body: RevealRequest,
) -> str:
    """Record the reveal and return the number. Commits. Raises 404, 422 or 429.

    Only an open account of PROVIDER or above is revealed, exactly as only such an account is
    listed and opened by id; anyone else is the same `404`. Nobody reveals their own number.
    """
    provider = visible_provider(db, provider_id)
    if provider.id == revealer.id:
        raise ApiError(422, "own_number", "This is your own number")
    # Lock the person's row so two parallel reveals cannot both slip under the limit. The second
    # request waits here, and its count then includes the first one's committed row. This relies
    # on PostgreSQL's default READ COMMITTED isolation (the project's setting): under REPEATABLE
    # READ the second request would still use its older snapshot and could exceed the limit. Keep
    # the default isolation level for this path, or retry on serialization failure.
    number = provider.mobile_number
    if number is None:  # an open account always has one (a database rule)
        raise ApiError(404, "not_found", "Provider not found")
    locks.lock_people(db, [revealer.id])
    check_reveal_limits(db, settings, revealer.id)
    db.add(
        PersonPhoneReveal(
            revealer_id=revealer.id,
            provider_id=provider.id,
            channel=body.channel,
            source=body.source,
            searched_skills=body.searched_skills or None,
        )
    )
    db.commit()
    return number
