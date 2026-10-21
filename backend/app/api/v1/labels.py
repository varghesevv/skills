import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_principal, require_roles
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.labels import Label
from app.schemas.common import LabelOut
from app.schemas.profiles import LabelCreate, LabelUpdate
from app.services.profiles import label_out

router = APIRouter(prefix="/labels", tags=["labels"])

AdminOnly = Annotated[Principal, Depends(require_roles("admin"))]


@router.get("")
def list_labels(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Session = Depends(get_session),
    label_type: Annotated[
        Literal["skill", "language", "timing", "nativity", "skill_level"] | None,
        Query(alias="type"),
    ] = None,
    include_inactive: bool = False,
) -> list[LabelOut]:
    query = select(Label).order_by(Label.label_type, Label.label_name)
    if label_type is not None:
        query = query.where(Label.label_type == label_type)
    if not (include_inactive and principal.user_type == "admin"):
        query = query.where(Label.is_active.is_(True))
    return [label_out(label) for label in db.scalars(query).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_label(body: LabelCreate, _: AdminOnly, db: Session = Depends(get_session)) -> LabelOut:
    label = Label(label_name=body.label_name.strip(), label_type=body.label_type)
    db.add(label)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "label_exists", "This label already exists") from None
    return label_out(label)


@router.patch("/{label_id}")
def update_label(
    label_id: uuid.UUID, body: LabelUpdate, _: AdminOnly, db: Session = Depends(get_session)
) -> LabelOut:
    """Rename or deactivate a label. Labels are never hard-deleted."""
    label = db.get(Label, label_id)
    if label is None:
        raise ApiError(404, "not_found", "Label not found")
    if body.label_name is not None:
        label.label_name = body.label_name.strip()
    if body.is_active is not None:
        label.is_active = body.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "label_exists", "This label already exists") from None
    return label_out(label)
