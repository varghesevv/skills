"""Provider search: filters, sorting and pagination in one SQL query, over people."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, func, literal, select, true
from sqlalchemy.orm import Session, aliased

from app.models.availability import PersonUnavailability
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK
from app.models.labels import Label, PersonLabel
from app.models.ratings import Rating
from app.schemas.church import IdName
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
    church_id: uuid.UUID | None = None
    home_group_id: uuid.UUID | None = None
    min_rating: float | None = None
    name: str | None = None
    sort: SortKey = "newest"


def _has_label(
    label_type: str, names: list[str] | None = None, level: str | None = None
) -> ColumnElement[bool]:
    """The person has a label of this type (with one of these names, at this level)."""
    link = aliased(PersonLabel)
    label = aliased(Label)
    stmt = (
        select(literal(1))
        .select_from(link)
        .join(label, label.id == link.label_id)
        .where(link.person_id == Person.id, label.label_type == label_type)
        .correlate(Person)
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
    # A person is searchable when their account is open and their status is PROVIDER or above
    # (a revoked person is below), and once there is at least one skill. A rate and ratings are
    # not needed, so newcomers are listed too (the rate filters simply do not match them).
    conditions: list[ColumnElement[bool]] = [
        Person.closed_at.is_(None),
        Person.status.in_(
            [s for s, rank in STATUS_RANK.items() if rank >= STATUS_RANK["provider"]]
        ),
        _has_label("skill"),
    ]
    name = filters.name.strip() if filters.name else ""
    if name:
        # A part of the name, any case; % and _ in the text are matched literally.
        escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(Person.full_name.ilike(f"%{escaped}%", escape="\\"))
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
        conditions.append(Person.rate_currency == filters.currency.upper())
    if filters.max_rate is not None:
        conditions.append(Person.rate_per_hour <= filters.max_rate)
    if filters.negotiable:
        conditions.append(Person.is_rate_negotiable.is_(True))

    if filters.available_from and filters.available_to:
        overlapping = (
            select(literal(1))
            .where(
                PersonUnavailability.person_id == Person.id,
                PersonUnavailability.unavailable_from < filters.available_to,
                PersonUnavailability.unavailable_to > filters.available_from,
            )
            .correlate(Person)
            .exists()
        )
        conditions.append(~overlapping)

    if filters.church_id is not None:
        conditions.append(Person.church_id == filters.church_id)
    if filters.home_group_id is not None:
        conditions.append(Person.home_group_id == filters.home_group_id)
    return conditions


def search_freelancers(
    db: Session, filters: SearchFilters, paging: Pagination
) -> Page[SearchResult]:
    stats = (
        select(
            func.avg(Rating.rating).label("avg_rating"),
            func.count(Rating.id).label("rating_count"),
        )
        .where(Rating.provider_id == Person.id)
        .correlate(Person)
        .lateral("rating_stats")
    )
    conditions = _conditions(filters)
    if filters.min_rating is not None:
        conditions.append(stats.c.avg_rating >= filters.min_rating)

    total = (
        db.scalar(select(func.count()).select_from(Person).join(stats, true()).where(*conditions))
        or 0
    )

    query: Select[tuple[Person, Decimal | None, int, str, str]] = (
        select(Person, stats.c.avg_rating, stats.c.rating_count, Church.name, HomeGroup.name)
        .select_from(Person)
        .join(stats, true())
        .join(Church, Church.id == Person.church_id)
        .join(HomeGroup, HomeGroup.id == Person.home_group_id)
        .where(*conditions)
    )
    order: list[ColumnElement[Any]]
    if filters.sort == "rating":
        order = [stats.c.avg_rating.desc().nulls_last(), stats.c.rating_count.desc()]
    elif filters.sort == "rate":
        order = [Person.rate_per_hour.asc().nulls_last()]
    else:
        order = [Person.created_at.desc()]
    rows = db.execute(
        query.order_by(*order, Person.id).offset(paging.offset).limit(paging.page_size)
    ).all()

    ids = [person.id for person, *_ in rows]
    skills: dict[uuid.UUID, list[SearchSkill]] = defaultdict(list)
    others: dict[uuid.UUID, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    if ids:
        level = aliased(Label)
        label_rows = db.execute(
            select(PersonLabel.person_id, Label.label_type, Label.label_name, level.label_name)
            .join(Label, Label.id == PersonLabel.label_id)
            .outerjoin(level, level.id == PersonLabel.level_label_id)
            .where(PersonLabel.person_id.in_(ids))
            .order_by(Label.label_name)
        ).all()
        for person_id, label_type, name, level_name in label_rows:
            if label_type == "skill":
                skills[person_id].append(SearchSkill(name=name, level=level_name))
            else:
                others[person_id][label_type].append(name)

    items = [
        SearchResult(
            id=person.id,
            full_name=person.full_name,
            church=IdName(id=person.church_id, name=church_name),
            home_group=IdName(id=person.home_group_id, name=group_name),
            nationality=person.nationality,
            primary_language=person.primary_language,
            whatsapp_availability=person.whatsapp_availability,
            rate_per_hour=to_float(person.rate_per_hour),
            rate_currency=person.rate_currency,
            is_rate_negotiable=person.is_rate_negotiable,
            average_rating=round(float(average), 2) if average is not None else None,
            rating_count=int(count),
            skills=skills[person.id],
            languages=others[person.id]["language"],
            timings=others[person.id]["timing"],
            nativity=others[person.id]["nativity"],
        )
        for person, average, count, church_name, group_name in rows
        if person.home_group_id is not None
    ]
    return Page[SearchResult](
        items=items, total=total, page=paging.page, page_size=paging.page_size
    )
