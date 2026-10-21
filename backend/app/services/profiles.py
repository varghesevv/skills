"""Shared helpers for the profile, label, vouching and rating endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import ApiError
from app.core.security import Principal
from app.models.labels import FreelancerLabel, Label
from app.models.ratings import UserRating
from app.schemas.common import LabelOut
from app.schemas.profiles import FreelancerLabelOut


def to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def current_account[M](db: Session, model: type[M], principal: Principal) -> M:
    """The logged-in user's own record (401 if the account no longer exists)."""
    account = db.get(model, principal.user_id)
    if account is None:
        raise ApiError(401, "invalid_token", "The account no longer exists")
    return account


def label_out(label: Label) -> LabelOut:
    return LabelOut(
        id=label.id,
        label_name=label.label_name,
        label_type=label.label_type,
        is_active=label.is_active,
    )


def freelancer_labels(db: Session, freelancer_id: uuid.UUID) -> list[FreelancerLabelOut]:
    level = aliased(Label)
    rows = db.execute(
        select(Label, level)
        .select_from(FreelancerLabel)
        .join(Label, Label.id == FreelancerLabel.label_id)
        .outerjoin(level, level.id == FreelancerLabel.level_label_id)
        .where(FreelancerLabel.freelancer_id == freelancer_id)
        .order_by(Label.label_type, Label.label_name)
    ).all()
    return [
        FreelancerLabelOut(
            label=label_out(label), level=label_out(lvl) if lvl is not None else None
        )
        for label, lvl in rows
    ]


def rating_summary(db: Session, freelancer_id: uuid.UUID) -> tuple[float | None, int]:
    average, count = db.execute(
        select(func.avg(UserRating.rating), func.count(UserRating.id)).where(
            UserRating.freelancer_id == freelancer_id
        )
    ).one()
    return (round(float(average), 2) if average is not None else None), int(count)


def utc_now() -> datetime:
    return datetime.now(UTC)
