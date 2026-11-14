import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.db import get_session
from app.core.errors import ApiError
from app.models.church import Person
from app.models.ratings import Rating
from app.schemas.profiles import GivenRating, RatingCreate, RatingUpdate
from app.services.locks import lock_people
from app.services.providers import visible_provider

router = APIRouter(prefix="/ratings", tags=["ratings"])

Rater = Annotated[Person, Depends(current_person("searcher"))]


def given_out(r: Rating, provider_name: str | None) -> GivenRating:
    return GivenRating(
        id=r.id,
        provider_id=r.provider_id,
        provider_name=provider_name,
        rating=r.rating,
        comment=r.comment,
        rated_on=r.rated_on,
        updated_at=r.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rating(
    body: RatingCreate, rater: Rater, db: Session = Depends(get_session)
) -> GivenRating:
    """Rate a provider 1 to 10. One rating per person and provider; use PUT to change it."""
    provider = visible_provider(db, body.provider_id)
    if provider.id == rater.id:
        raise ApiError(422, "cannot_rate_self", "You cannot rate yourself")
    row = Rating(
        rater_id=rater.id, provider_id=provider.id, rating=body.rating, comment=body.comment
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "already_rated", "You already rated this provider; update that rating instead"
        ) from None
    return given_out(row, provider.full_name)


@router.put("/{rating_id}")
def update_rating(
    rating_id: uuid.UUID,
    body: RatingUpdate,
    rater: Rater,
    db: Session = Depends(get_session),
) -> GivenRating:
    # Lock the person while their rating changes, so a double submit is one change after another.
    lock_people(db, [rater.id])
    row = db.get(Rating, rating_id)
    if row is None or row.rater_id != rater.id:
        raise ApiError(404, "not_found", "Rating not found")
    row.rating = body.rating
    row.comment = body.comment
    db.commit()
    provider = db.get(Person, row.provider_id)
    return given_out(row, provider.full_name if provider else None)
