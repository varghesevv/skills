from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_session
from app.core.security import Principal
from app.models.ratings import UserRating
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
    host.mobile_number = body.mobile_number
    for day in DAYS:
        setattr(host, f"avail_{day}", day in body.available_days)
    db.commit()
    return _response(host)


@router.get("/me/ratings")
def my_ratings(
    principal: HostOnly,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
) -> Page[GivenRating]:
    where = UserRating.work_host_id == principal.user_id
    total = db.scalar(select(func.count()).select_from(UserRating).where(where)) or 0
    rows = db.scalars(
        select(UserRating)
        .where(where)
        .order_by(UserRating.rated_on.desc(), UserRating.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[GivenRating](
        items=[
            GivenRating(
                id=r.id,
                freelancer_id=r.freelancer_id,
                rating=r.rating,
                comment=r.comment,
                rated_on=r.rated_on,
                updated_at=r.updated_at,
            )
            for r in rows
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
