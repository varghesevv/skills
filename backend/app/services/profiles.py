"""Shared helpers for the profile, label, vouching and rating endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.labels import Label, PersonLabel
from app.models.ratings import Rating
from app.schemas.common import LabelOut
from app.schemas.profiles import FreelancerLabelOut


def to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def label_out(label: Label) -> LabelOut:
    return LabelOut(
        id=label.id,
        label_name=label.label_name,
        label_type=label.label_type,
        is_active=label.is_active,
    )


def person_labels(db: Session, person_id: uuid.UUID) -> list[FreelancerLabelOut]:
    """The labels a person has chosen for their provider profile, with skill levels."""
    level = aliased(Label)
    rows = db.execute(
        select(Label, level)
        .select_from(PersonLabel)
        .join(Label, Label.id == PersonLabel.label_id)
        .outerjoin(level, level.id == PersonLabel.level_label_id)
        .where(PersonLabel.person_id == person_id)
        .order_by(Label.label_type, Label.label_name)
    ).all()
    return [
        FreelancerLabelOut(
            label=label_out(label), level=label_out(lvl) if lvl is not None else None
        )
        for label, lvl in rows
    ]


def person_rating_summary(db: Session, provider_id: uuid.UUID) -> tuple[float | None, int]:
    average, count = db.execute(
        select(func.avg(Rating.rating), func.count(Rating.id)).where(
            Rating.provider_id == provider_id
        )
    ).one()
    return (round(float(average), 2) if average is not None else None), int(count)


def utc_now() -> datetime:
    return datetime.now(UTC)
