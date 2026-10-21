import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.users import Organisation
from app.schemas.auth import OrganisationPage, OrganisationSummary

router = APIRouter(prefix="/admin", tags=["admin"])

AdminOnly = Annotated[Principal, Depends(require_roles("admin"))]


def _summary(org: Organisation) -> OrganisationSummary:
    return OrganisationSummary(
        id=org.id,
        org_name=org.org_name,
        email=org.user_email,
        mobile_number=org.mobile_number,
        approval_status=org.approval_status,
        created_at=org.created_at,
    )


@router.get("/organisations")
def list_organisations(
    _: AdminOnly,
    db: Session = Depends(get_session),
    status: Literal["pending", "approved", "rejected"] = "pending",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrganisationPage:
    where = Organisation.approval_status == status
    total = db.scalar(select(func.count()).select_from(Organisation).where(where)) or 0
    rows = db.scalars(
        select(Organisation)
        .where(where)
        .order_by(Organisation.created_at, Organisation.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OrganisationPage(
        items=[_summary(row) for row in rows], total=total, page=page, page_size=page_size
    )


def _decide(db: Session, admin: Principal, org_id: uuid.UUID, decision: str) -> OrganisationSummary:
    org = db.get(Organisation, org_id)
    if org is None:
        raise ApiError(404, "not_found", "Organisation not found")
    org.approval_status = decision
    org.approved_at = datetime.now(UTC)
    org.approved_by_admin_id = admin.user_id
    db.commit()
    return _summary(org)


@router.post("/organisations/{org_id}/approve")
def approve_organisation(
    org_id: uuid.UUID, admin: AdminOnly, db: Session = Depends(get_session)
) -> OrganisationSummary:
    return _decide(db, admin, org_id, "approved")


@router.post("/organisations/{org_id}/reject")
def reject_organisation(
    org_id: uuid.UUID, admin: AdminOnly, db: Session = Depends(get_session)
) -> OrganisationSummary:
    return _decide(db, admin, org_id, "rejected")
