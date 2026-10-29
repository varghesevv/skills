"""Revealing a freelancer's mobile number: the limits, the lock and the record of each reveal."""

import math
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.models.reveals import PhoneReveal
from app.models.users import Freelancer, WorkHost
from app.schemas.profiles import RevealRequest
from app.services.profiles import utc_now


def check_reveal_limits(db: Session, settings: Settings, host_id: uuid.UUID) -> None:
    """Answer 429 when this work host has asked for too many numbers lately.

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
            select(PhoneReveal.revealed_at)
            .where(PhoneReveal.work_host_id == host_id, PhoneReveal.revealed_at > now - window)
            .order_by(PhoneReveal.revealed_at.desc())
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
    host_id: uuid.UUID,
    freelancer_id: uuid.UUID,
    body: RevealRequest,
) -> str:
    """Record the reveal and return the number. Commits. Raises 404 or 429.

    Any freelancer with an account can be revealed, exactly as any freelancer's profile can be
    opened by id: freelancers have no approval or active flag (only organisations do).
    """
    freelancer = db.get(Freelancer, freelancer_id)
    if freelancer is None:
        raise ApiError(404, "not_found", "Freelancer not found")
    # Lock the work host's row so two parallel reveals cannot both slip under the limit. The
    # second request waits here, and its count then includes the first one's committed row.
    # This relies on PostgreSQL's default READ COMMITTED isolation (the project's setting): under
    # REPEATABLE READ the second request would still use its older snapshot and could exceed the
    # limit. Keep the default isolation level for this path, or retry on serialization failure.
    db.execute(select(WorkHost.id).where(WorkHost.id == host_id).with_for_update())
    check_reveal_limits(db, settings, host_id)
    db.add(
        PhoneReveal(
            work_host_id=host_id,
            freelancer_id=freelancer.id,
            channel=body.channel,
            source=body.source,
            searched_skills=body.searched_skills or None,
        )
    )
    number = freelancer.mobile_number
    db.commit()
    return number
