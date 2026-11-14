from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_person, require_roles
from app.api.v1.ratings import given_out
from app.core.db import get_session
from app.core.security import Principal
from app.models.church import Person
from app.models.ratings import Rating
from app.models.users import WorkHost
from app.schemas.common import Page, Pagination, pagination
from app.schemas.profiles import DAYS, GivenRating, WorkHostMe, WorkHostUpdate
from app.services.profiles import current_account

router = APIRouter(prefix="/workhosts", tags=["work hosts"])

HostOnly = Annotated[Principal, Depends(require_roles("workhost"))]


def _response(host: WorkHost) -> WorkHostMe:
    days = [day for day in DAYS if getattr(host, f"avail_{day}")]
    return WorkHostMe(
        id=host.id,
        full_name=host.full_name,
        email=host.user_email,
        mobile_number=host.mobile_number,
        available_days=days,
        created_at=host.created_at,
    )


@router.get("/me")
def get_me(principal: HostOnly, db: Session = Depends(get_session)) -> WorkHostMe:
    return _response(current_account(db, WorkHost, principal))


@router.put("/me")
def update_me(
    body: WorkHostUpdate, principal: HostOnly, db: Session = Depends(get_session)
) -> WorkHostMe:
    host = current_account(db, WorkHost, principal)
    if body.full_name is not None:
        host.full_name = body.full_name
    host.mobile_number = body.mobile_number
    for day in DAYS:
        setattr(host, f"avail_{day}", day in body.available_days)
    db.commit()
    return _response(host)


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
