import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.users import Freelancer, Organisation
from app.models.vouching import OrgFreelancer
from app.schemas.common import Page, Pagination, pagination
from app.schemas.profiles import (
    OrganisationBrief,
    OrganisationMe,
    OrganisationUpdate,
    VouchedFreelancer,
)
from app.services.profiles import current_account

router = APIRouter(prefix="/organisations", tags=["organisations"])

OrgOnly = Annotated[Principal, Depends(require_roles("organisation"))]
DirectoryReader = Annotated[Principal, Depends(require_roles("workhost", "organisation", "admin"))]

DIRECTORY_LIMIT = 500


def _response(org: Organisation) -> OrganisationMe:
    return OrganisationMe(
        id=org.id,
        email=org.user_email,
        org_name=org.org_name,
        mobile_number=org.mobile_number,
        approval_status=org.approval_status,
        created_at=org.created_at,
    )


def _vouched(link: OrgFreelancer, freelancer: Freelancer) -> VouchedFreelancer:
    return VouchedFreelancer(
        freelancer_id=freelancer.id,
        full_name=freelancer.full_name,
        nationality=freelancer.nationality,
        primary_language=freelancer.primary_language,
        status=link.status,
        is_active=link.is_active,
        created_at=link.created_at,
    )


@router.get("")
def directory(_: DirectoryReader, db: Session = Depends(get_session)) -> list[OrganisationBrief]:
    """Approved organisations by name, so work hosts can filter a search by who vouches."""
    rows = db.execute(
        select(Organisation.id, Organisation.org_name)
        .where(Organisation.approval_status == "approved")
        .order_by(Organisation.org_name, Organisation.id)
        .limit(DIRECTORY_LIMIT)
    ).all()
    return [OrganisationBrief(id=row.id, org_name=row.org_name) for row in rows]


@router.get("/me")
def get_me(principal: OrgOnly, db: Session = Depends(get_session)) -> OrganisationMe:
    return _response(current_account(db, Organisation, principal))


@router.put("/me")
def update_me(
    body: OrganisationUpdate, principal: OrgOnly, db: Session = Depends(get_session)
) -> OrganisationMe:
    org = current_account(db, Organisation, principal)
    org.org_name = body.org_name
    org.mobile_number = body.mobile_number
    db.commit()
    return _response(org)


@router.get("/me/freelancers")
def list_freelancers(
    principal: OrgOnly,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
) -> Page[VouchedFreelancer]:
    where = OrgFreelancer.org_id == principal.user_id
    total = db.scalar(select(func.count()).select_from(OrgFreelancer).where(where)) or 0
    rows = db.execute(
        select(OrgFreelancer, Freelancer)
        .join(Freelancer, Freelancer.id == OrgFreelancer.freelancer_id)
        .where(where)
        .order_by(OrgFreelancer.created_at, Freelancer.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[VouchedFreelancer](
        items=[_vouched(link, freelancer) for link, freelancer in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("/me/freelancers/{freelancer_id}", status_code=status.HTTP_201_CREATED)
def vouch(
    freelancer_id: uuid.UUID, principal: OrgOnly, db: Session = Depends(get_session)
) -> VouchedFreelancer:
    """Vouch for a freelancer. The vouch stays pending until the freelancer accepts it."""
    org = current_account(db, Organisation, principal)
    if org.approval_status != "approved":
        raise ApiError(403, "organisation_not_approved", "The organisation is not approved")
    freelancer = db.get(Freelancer, freelancer_id)
    if freelancer is None:
        raise ApiError(404, "not_found", "Freelancer not found")
    link = db.get(OrgFreelancer, (org.id, freelancer_id))
    if link is None:
        link = OrgFreelancer(org_id=org.id, freelancer_id=freelancer_id)
        db.add(link)
    elif link.status != "revoked":
        raise ApiError(409, "already_vouched", "You already vouch for this freelancer")
    else:  # vouching again after a revoke starts over as pending
        link.status = "pending"
        link.is_active = True
    db.commit()
    db.refresh(link)
    return _vouched(link, freelancer)


@router.delete("/me/freelancers/{freelancer_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(
    freelancer_id: uuid.UUID, principal: OrgOnly, db: Session = Depends(get_session)
) -> Response:
    link = db.get(OrgFreelancer, (principal.user_id, freelancer_id))
    if link is None:
        raise ApiError(404, "not_found", "You do not vouch for this freelancer")
    link.status = "revoked"
    link.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
