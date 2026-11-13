import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import client_address, current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.church import Person
from app.schemas.vouching import VouchCreated, VouchLinkInfo, VouchLinkToken
from app.services import vouching
from app.services.rate_limit import link_lookup_limiter, vouch_attempt_limiter

router = APIRouter(tags=["vouching"])

# Anyone admitted may vouch: a SEARCHER or higher, in any church.
Voucher = Annotated[Person, Depends(current_person("searcher"))]


@router.post("/vouch-links/lookup")
def lookup_vouch_link(
    body: VouchLinkToken,
    request: Request,
    voucher: Voucher,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VouchLinkInfo:
    """Who a vouch link is for. The token is in the body, not the path, so it never reaches an
    access log of the API. Rate limited per IP; every failure is the same `404`."""
    link_lookup_limiter.check(client_address(request), settings.link_lookup_max_per_hour)
    return vouching.link_info(db, voucher, body.token)


@router.post("/vouch-links/vouch", status_code=status.HTTP_201_CREATED)
def vouch_through_link(
    body: VouchLinkToken,
    request: Request,
    voucher: Voucher,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VouchCreated:
    """Vouch for the person the link is for: once each, never for yourself, and at most
    `VOUCH_MAX_PER_DAY` a day."""
    vouch_attempt_limiter.check(client_address(request), settings.link_lookup_max_per_hour)
    created = vouching.vouch(db, settings, voucher, body.token)
    return VouchCreated(id=created.id)


@router.delete("/vouches/{vouch_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_vouch(
    vouch_id: uuid.UUID, voucher: Voucher, db: Annotated[Session, Depends(get_session)]
) -> Response:
    """Take back your vouch, until the applicant is admitted."""
    vouching.withdraw(db, voucher, vouch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
