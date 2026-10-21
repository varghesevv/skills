import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.ratings import UserRating
from app.models.users import Freelancer
from app.schemas.profiles import GivenRating, RatingCreate, RatingUpdate

router = APIRouter(prefix="/ratings", tags=["ratings"])

HostOnly = Annotated[Principal, Depends(require_roles("workhost"))]


def _out(r: UserRating) -> GivenRating:
    return GivenRating(
        id=r.id,
        freelancer_id=r.freelancer_id,
        rating=r.rating,
        comment=r.comment,
        rated_on=r.rated_on,
        updated_at=r.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rating(
    body: RatingCreate, principal: HostOnly, db: Session = Depends(get_session)
) -> GivenRating:
    """Rate a freelancer 1 to 10. One rating per work host and freelancer; use PUT to change it."""
    if db.get(Freelancer, body.freelancer_id) is None:
        raise ApiError(404, "not_found", "Freelancer not found")
    row = UserRating(
        work_host_id=principal.user_id,
        freelancer_id=body.freelancer_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "already_rated", "You already rated this freelancer; update that rating instead"
        ) from None
    return _out(row)


@router.put("/{rating_id}")
def update_rating(
    rating_id: uuid.UUID,
    body: RatingUpdate,
    principal: HostOnly,
    db: Session = Depends(get_session),
) -> GivenRating:
    row = db.get(UserRating, rating_id)
    if row is None or row.work_host_id != principal.user_id:
        raise ApiError(404, "not_found", "Rating not found")
    row.rating = body.rating
    row.comment = body.comment
    db.commit()
    return _out(row)
