from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.api.v1.ratings import given_out
from app.core.db import get_session
from app.models.church import Person
from app.models.ratings import Rating
from app.schemas.common import Page, Pagination, pagination
from app.schemas.profiles import GivenRating

router = APIRouter(prefix="/workhosts", tags=["ratings"])


@router.get("/me/ratings")
def my_ratings(
    rater: Annotated[Person, Depends(current_person("searcher"))],
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
) -> Page[GivenRating]:
    """The ratings the caller gave (a SEARCHER or above). The path keeps its older name."""
    where = Rating.rater_id == rater.id
    total = db.scalar(select(func.count()).select_from(Rating).where(where)) or 0
    rows = db.execute(
        select(Rating, Person.full_name)
        .join(Person, Person.id == Rating.provider_id)
        .where(where)
        .order_by(Rating.rated_on.desc(), Rating.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[GivenRating](
        items=[given_out(r, name) for r, name in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
