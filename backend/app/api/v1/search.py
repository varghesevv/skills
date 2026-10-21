import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.schemas.common import Page, Pagination, pagination
from app.schemas.search import SearchResult
from app.services.search import SearchFilters, SortKey, search_freelancers

router = APIRouter(prefix="/search", tags=["search"])

Searcher = Annotated[Principal, Depends(require_roles("workhost", "organisation", "admin"))]
Names = Annotated[list[str] | None, Query(max_length=20)]


@router.get("/freelancers")
def search(
    _: Searcher,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
    skill: Names = None,
    skill_match: Literal["any", "all"] = "any",
    skill_level: Annotated[str | None, Query(max_length=100)] = None,
    language: Names = None,
    timing: Names = None,
    nativity: Names = None,
    max_rate: Annotated[Decimal | None, Query(ge=0)] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    negotiable: bool = False,
    available_from: AwareDatetime | None = None,
    available_to: AwareDatetime | None = None,
    org_id: uuid.UUID | None = None,
    min_rating: Annotated[float | None, Query(ge=1, le=10)] = None,
    sort: SortKey = "newest",
) -> Page[SearchResult]:
    """Find freelancers. Only complete profiles (a rate and at least one skill) are listed."""
    if max_rate is not None and currency is None:
        raise ApiError(422, "currency_required", "max_rate needs a currency, for example AED")
    if (available_from is None) != (available_to is None):
        raise ApiError(
            422, "availability_range", "available_from and available_to must be given together"
        )
    start: datetime | None = available_from
    end: datetime | None = available_to
    if start is not None and end is not None and start >= end:
        raise ApiError(422, "availability_range", "available_from must be before available_to")
    filters = SearchFilters(
        skills=skill or [],
        skill_match=skill_match,
        skill_level=skill_level,
        languages=language or [],
        timings=timing or [],
        nativity=nativity or [],
        max_rate=max_rate,
        currency=currency,
        negotiable=negotiable,
        available_from=start,
        available_to=end,
        org_id=org_id,
        min_rating=min_rating,
        sort=sort,
    )
    return search_freelancers(db, filters, paging)
