"""Freelancer search: filters, sorting and pagination in one SQL query."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, func, literal, select, true
from sqlalchemy.orm import Session, aliased

from app.models.availability import FreelancerUnavailability
from app.models.labels import FreelancerLabel, Label
from app.models.ratings import UserRating
from app.models.users import Freelancer
from app.models.vouching import OrgFreelancer
from app.schemas.common import Page, Pagination
from app.schemas.search import SearchResult, SearchSkill
from app.services.profiles import to_float

SortKey = Literal["rating", "rate", "newest"]


@dataclass
class SearchFilters:
    skills: list[str] = field(default_factory=list)
    skill_match: Literal["any", "all"] = "any"
    skill_level: str | None = None
    languages: list[str] = field(default_factory=list)
    timings: list[str] = field(default_factory=list)
    nativity: list[str] = field(default_factory=list)
    max_rate: Decimal | None = None
    currency: str | None = None
    negotiable: bool = False
    available_from: datetime | None = None
    available_to: datetime | None = None
    org_id: uuid.UUID | None = None
    min_rating: float | None = None
    sort: SortKey = "newest"


def _has_label(
    label_type: str, names: list[str] | None = None, level: str | None = None
) -> ColumnElement[bool]:
    """The freelancer has a label of this type (with one of these names, at this level)."""
    link = aliased(FreelancerLabel)
    label = aliased(Label)
    stmt = (
        select(literal(1))
        .select_from(link)
        .join(label, label.id == link.label_id)
        .where(link.freelancer_id == Freelancer.id, label.label_type == label_type)
        .correlate(Freelancer)
    )
    if names is not None:
        stmt = stmt.where(func.lower(label.label_name).in_(names))
    if level is not None:
        skill_level = aliased(Label)
        stmt = stmt.join(skill_level, skill_level.id == link.level_label_id).where(
            func.lower(skill_level.label_name) == level
        )
    return stmt.exists()


def _lower(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]


def _conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
    # Only complete profiles are searchable: a rate and at least one skill.
    conditions: list[ColumnElement[bool]] = [
        Freelancer.rate_per_hour.is_not(None),
        _has_label("skill"),
    ]
    level = filters.skill_level.strip().lower() if filters.skill_level else None
    skills = _lower(filters.skills)
    if skills and filters.skill_match == "all":
        conditions.extend(_has_label("skill", [name], level) for name in dict.fromkeys(skills))
    elif skills:
        conditions.append(_has_label("skill", skills, level))
    elif level:
        conditions.append(_has_label("skill", None, level))

    for label_type, values in (
        ("language", filters.languages),
        ("timing", filters.timings),
        ("nativity", filters.nativity),
    ):
        names = _lower(values)
        if names:
            conditions.append(_has_label(label_type, names))

    if filters.currency:
        conditions.append(Freelancer.rate_currency == filters.currency.upper())
    if filters.max_rate is not None:
        conditions.append(Freelancer.rate_per_hour <= filters.max_rate)
    if filters.negotiable:
        conditions.append(Freelancer.is_rate_negotiable.is_(True))

    if filters.available_from and filters.available_to:
        overlapping = (
            select(literal(1))
            .where(
                FreelancerUnavailability.freelancer_id == Freelancer.id,
                FreelancerUnavailability.unavailable_from < filters.available_to,
                FreelancerUnavailability.unavailable_to > filters.available_from,
            )
            .correlate(Freelancer)
            .exists()
        )
        conditions.append(~overlapping)

    if filters.org_id is not None:
        conditions.append(
            select(literal(1))
            .where(
                OrgFreelancer.freelancer_id == Freelancer.id,
                OrgFreelancer.org_id == filters.org_id,
                OrgFreelancer.status == "approved",
                OrgFreelancer.is_active.is_(True),
            )
            .correlate(Freelancer)
            .exists()
        )
    return conditions


def search_freelancers(
    db: Session, filters: SearchFilters, paging: Pagination
) -> Page[SearchResult]:
    stats = (
        select(
            func.avg(UserRating.rating).label("avg_rating"),
            func.count(UserRating.id).label("rating_count"),
        )
        .where(UserRating.freelancer_id == Freelancer.id)
        .correlate(Freelancer)
        .lateral("rating_stats")
    )
    conditions = _conditions(filters)
    if filters.min_rating is not None:
        conditions.append(stats.c.avg_rating >= filters.min_rating)

    total = (
        db.scalar(
            select(func.count()).select_from(Freelancer).join(stats, true()).where(*conditions)
        )
        or 0
    )

    query: Select[tuple[Freelancer, Decimal | None, int]] = (
        select(Freelancer, stats.c.avg_rating, stats.c.rating_count)
        .join(stats, true())
        .where(*conditions)
    )
    order: list[ColumnElement[Any]]
    if filters.sort == "rating":
        order = [stats.c.avg_rating.desc().nulls_last(), stats.c.rating_count.desc()]
    elif filters.sort == "rate":
        order = [Freelancer.rate_per_hour.asc()]
    else:
        order = [Freelancer.created_at.desc()]
    rows = db.execute(
        query.order_by(*order, Freelancer.id).offset(paging.offset).limit(paging.page_size)
    ).all()

    ids = [freelancer.id for freelancer, _, _ in rows]
    skills: dict[uuid.UUID, list[SearchSkill]] = defaultdict(list)
    others: dict[uuid.UUID, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    vouches: dict[uuid.UUID, int] = {}
    if ids:
        level = aliased(Label)
        label_rows = db.execute(
            select(
                FreelancerLabel.freelancer_id,
                Label.label_type,
                Label.label_name,
                level.label_name,
            )
            .join(Label, Label.id == FreelancerLabel.label_id)
            .outerjoin(level, level.id == FreelancerLabel.level_label_id)
            .where(FreelancerLabel.freelancer_id.in_(ids))
            .order_by(Label.label_name)
        ).all()
        for freelancer_id, label_type, name, level_name in label_rows:
            if label_type == "skill":
                skills[freelancer_id].append(SearchSkill(name=name, level=level_name))
            else:
                others[freelancer_id][label_type].append(name)
        vouch_rows = db.execute(
            select(OrgFreelancer.freelancer_id, func.count())
            .where(
                OrgFreelancer.freelancer_id.in_(ids),
                OrgFreelancer.status == "approved",
                OrgFreelancer.is_active.is_(True),
            )
            .group_by(OrgFreelancer.freelancer_id)
        ).all()
        vouches = {freelancer_id: int(total) for freelancer_id, total in vouch_rows}

    items = [
        SearchResult(
            id=freelancer.id,
            full_name=freelancer.full_name,
            nationality=freelancer.nationality,
            primary_language=freelancer.primary_language,
            whatsapp_availability=freelancer.whatsapp_availability,
            rate_per_hour=to_float(freelancer.rate_per_hour),
            rate_currency=freelancer.rate_currency,
            is_rate_negotiable=freelancer.is_rate_negotiable,
            average_rating=round(float(average), 2) if average is not None else None,
            rating_count=int(count),
            vouch_count=vouches.get(freelancer.id, 0),
            skills=skills[freelancer.id],
            languages=others[freelancer.id]["language"],
            timings=others[freelancer.id]["timing"],
            nativity=others[freelancer.id]["nativity"],
        )
        for freelancer, average, count in rows
    ]
    return Page[SearchResult](
        items=items, total=total, page=paging.page, page_size=paging.page_size
    )
