import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.models.availability import PersonUnavailability
from app.models.church import Church, HomeGroup, Person
from app.models.labels import Label, PersonLabel
from app.models.ratings import Rating
from app.schemas.church import IdName
from app.schemas.common import Page, Pagination, pagination
from app.schemas.profiles import (
    FreelancerLabelOut,
    FreelancerMe,
    FreelancerPublic,
    FreelancerUpdate,
    GivenRating,
    LabelsUpdate,
    PublicRating,
    RevealedMobile,
    RevealRequest,
    UnavailabilityIn,
    UnavailabilityOut,
)
from app.services.locks import lock_people
from app.services.profiles import (
    person_labels,
    person_rating_summary,
    to_float,
    utc_now,
)
from app.services.providers import visible_provider
from app.services.reveals import reveal_mobile_number

router = APIRouter(prefix="/freelancers", tags=["freelancers"])

ProviderOrAbove = Annotated[Person, Depends(current_person("provider"))]


def _me_response(db: Session, me: Person) -> FreelancerMe:
    return FreelancerMe(
        id=me.id,
        full_name=me.full_name,
        email=me.email or "",
        mobile_number=me.mobile_number or "",
        whatsapp_availability=me.whatsapp_availability,
        nationality=me.nationality,
        primary_language=me.primary_language,
        rate_per_hour=to_float(me.rate_per_hour),
        rate_currency=me.rate_currency,
        is_rate_negotiable=me.is_rate_negotiable,
        labels=person_labels(db, me.id),
        created_at=me.created_at,
    )


# ---- own profile (the person's, for a provider or above) ----------------------------------


@router.get("/me")
def get_me(provider: ProviderOrAbove, db: Session = Depends(get_session)) -> FreelancerMe:
    return _me_response(db, provider)


@router.put("/me")
def update_me(
    body: FreelancerUpdate, provider: ProviderOrAbove, db: Session = Depends(get_session)
) -> FreelancerMe:
    if body.full_name is not None:
        provider.full_name = body.full_name
    provider.mobile_number = body.mobile_number
    provider.whatsapp_availability = body.whatsapp_availability
    provider.nationality = body.nationality
    provider.primary_language = body.primary_language
    provider.rate_per_hour = body.rate_per_hour
    provider.rate_currency = body.rate_currency
    provider.is_rate_negotiable = body.is_rate_negotiable
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "account_exists", "An account with these details already exists"
        ) from None
    return _me_response(db, provider)


@router.put("/me/labels")
def replace_labels(
    body: LabelsUpdate, provider: ProviderOrAbove, db: Session = Depends(get_session)
) -> list[FreelancerLabelOut]:
    """Replace the person's whole label set. Skill levels attach to a specific skill."""
    chosen = [selection.label_id for selection in body.labels]
    if len(set(chosen)) != len(chosen):
        raise ApiError(422, "duplicate_label", "A label was selected more than once")
    wanted = set(chosen) | {s.level_label_id for s in body.labels if s.level_label_id}
    active_labels = db.scalars(select(Label).where(Label.id.in_(wanted), Label.is_active.is_(True)))
    found = {label.id: label for label in active_labels}
    if wanted - found.keys():
        raise ApiError(422, "unknown_label", "A label does not exist or is not active")
    for selection in body.labels:
        label = found[selection.label_id]
        if label.label_type == "skill_level":
            raise ApiError(
                422, "level_not_selectable", "A skill level can only be attached to a skill"
            )
        if selection.level_label_id is not None and (
            label.label_type != "skill"
            or found[selection.level_label_id].label_type != "skill_level"
        ):
            raise ApiError(
                422, "invalid_level", "Only skills take a level, and it must be a skill level"
            )
    # One replacement at a time per person: a double submit waits instead of failing on the key.
    lock_people(db, [provider.id])
    db.execute(delete(PersonLabel).where(PersonLabel.person_id == provider.id))
    db.add_all(
        PersonLabel(person_id=provider.id, label_id=s.label_id, level_label_id=s.level_label_id)
        for s in body.labels
    )
    db.commit()
    return person_labels(db, provider.id)


# ---- unavailability -----------------------------------------------------------------------


def _unavailability_out(row: PersonUnavailability) -> UnavailabilityOut:
    return UnavailabilityOut(
        id=row.id, unavailable_from=row.unavailable_from, unavailable_to=row.unavailable_to
    )


def _commit_unavailability(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "unavailability_overlaps", "This period overlaps one you already have"
        ) from None


def _own_period(db: Session, me: Person, period_id: uuid.UUID) -> PersonUnavailability:
    row = db.get(PersonUnavailability, period_id)
    if row is None or row.person_id != me.id:
        raise ApiError(404, "not_found", "Unavailability period not found")
    return row


@router.get("/me/unavailability")
def list_unavailability(
    provider: ProviderOrAbove, db: Session = Depends(get_session)
) -> list[UnavailabilityOut]:
    rows = db.scalars(
        select(PersonUnavailability)
        .where(PersonUnavailability.person_id == provider.id)
        .order_by(PersonUnavailability.unavailable_from)
    ).all()
    return [_unavailability_out(row) for row in rows]


@router.post("/me/unavailability", status_code=status.HTTP_201_CREATED)
def add_unavailability(
    body: UnavailabilityIn, provider: ProviderOrAbove, db: Session = Depends(get_session)
) -> UnavailabilityOut:
    row = PersonUnavailability(
        person_id=provider.id,
        unavailable_from=body.unavailable_from,
        unavailable_to=body.unavailable_to,
    )
    db.add(row)
    _commit_unavailability(db)
    return _unavailability_out(row)


@router.put("/me/unavailability/{period_id}")
def update_unavailability(
    period_id: uuid.UUID,
    body: UnavailabilityIn,
    provider: ProviderOrAbove,
    db: Session = Depends(get_session),
) -> UnavailabilityOut:
    row = _own_period(db, provider, period_id)
    row.unavailable_from = body.unavailable_from
    row.unavailable_to = body.unavailable_to
    _commit_unavailability(db)
    return _unavailability_out(row)


@router.delete("/me/unavailability/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unavailability(
    period_id: uuid.UUID, provider: ProviderOrAbove, db: Session = Depends(get_session)
) -> Response:
    db.delete(_own_period(db, provider, period_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- what others see (a SEARCHER or above looks at an open PROVIDER or above) ---------------

Searcher = Annotated[Person, Depends(current_person("searcher"))]


def _given(rating: Rating, provider_name: str | None) -> GivenRating:
    return GivenRating(
        id=rating.id,
        provider_id=rating.provider_id,
        provider_name=provider_name,
        rating=rating.rating,
        comment=rating.comment,
        rated_on=rating.rated_on,
        updated_at=rating.updated_at,
    )


@router.get("/{freelancer_id}")
def public_profile(
    freelancer_id: uuid.UUID, viewer: Searcher, db: Session = Depends(get_session)
) -> FreelancerPublic:
    provider = visible_provider(db, freelancer_id)
    average, count = person_rating_summary(db, provider.id)
    church = db.get(Church, provider.church_id)
    group = db.get(HomeGroup, provider.home_group_id) if provider.home_group_id else None
    if church is None or group is None:  # an open provider always has both (database rules)
        raise ApiError(404, "not_found", "Provider not found")
    upcoming = db.scalars(
        select(PersonUnavailability)
        .where(
            PersonUnavailability.person_id == provider.id,
            PersonUnavailability.unavailable_to > utc_now(),
        )
        .order_by(PersonUnavailability.unavailable_from)
    ).all()
    given = db.scalar(
        select(Rating).where(Rating.rater_id == viewer.id, Rating.provider_id == provider.id)
    )
    return FreelancerPublic(
        id=provider.id,
        full_name=provider.full_name,
        whatsapp_availability=provider.whatsapp_availability,
        nationality=provider.nationality,
        primary_language=provider.primary_language,
        rate_per_hour=to_float(provider.rate_per_hour),
        rate_currency=provider.rate_currency,
        is_rate_negotiable=provider.is_rate_negotiable,
        labels=person_labels(db, provider.id),
        average_rating=average,
        rating_count=count,
        church=IdName(id=church.id, name=church.name),
        home_group=IdName(id=group.id, name=group.name),
        unavailable=[_unavailability_out(row) for row in upcoming],
        my_rating=_given(given, provider.full_name) if given is not None else None,
    )


@router.post("/{freelancer_id}/reveal-mobile")
def reveal_mobile(
    freelancer_id: uuid.UUID,
    body: RevealRequest,
    viewer: Searcher,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RevealedMobile:
    """The only place a provider's mobile number is returned to a member (the leaders' own
    screens are the other, and are logged).

    Every call is recorded, and each person has an hourly and a daily limit.
    """
    number = reveal_mobile_number(
        db, settings, revealer=viewer, provider_id=freelancer_id, body=body
    )
    response.headers["Cache-Control"] = "no-store"
    return RevealedMobile(mobile_number=number)


@router.get("/{freelancer_id}/ratings")
def freelancer_ratings(
    freelancer_id: uuid.UUID,
    _: Searcher,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
) -> Page[PublicRating]:
    provider = visible_provider(db, freelancer_id)
    where = Rating.provider_id == provider.id
    total = db.scalar(select(func.count()).select_from(Rating).where(where)) or 0
    rows = db.scalars(
        select(Rating)
        .where(where)
        .order_by(Rating.rated_on.desc(), Rating.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[PublicRating](
        items=[PublicRating(rating=r.rating, comment=r.comment, rated_on=r.rated_on) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
