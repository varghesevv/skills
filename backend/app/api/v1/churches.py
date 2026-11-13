import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import client_address, current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.models.church import Person
from app.schemas.church import ChurchList, HomeGroupList, IdName
from app.schemas.home_groups import AdminChange, AdminChanged
from app.services import directory, succession
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/churches", tags=["churches"])

# Open to everyone (the sign-up screen has no account yet), so limited per IP address.
limiter = SlidingWindowLimiter(
    60, code="rate_limited", message="Too many requests. Try again in a moment."
)


def _limit(request: Request, settings: Settings) -> None:
    limiter.check(client_address(request), settings.public_list_max_per_minute)


@router.get("")
def list_churches(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChurchList:
    """Public: the open churches by name. No contact details."""
    _limit(request, settings)
    return ChurchList(items=directory.open_churches(db))


@router.get("/{church_id}/home-groups")
def list_home_groups(
    church_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HomeGroupList:
    """Public: the open home groups of an open church, each with its leader's name."""
    _limit(request, settings)
    groups = directory.open_home_groups(db, church_id)
    if groups is None:
        raise ApiError(404, "not_found", "There is no such church")
    return HomeGroupList(items=groups)


@router.put("/{church_id}/admin")
def change_admin(
    church_id: uuid.UUID,
    body: AdminChange,
    owner: Annotated[Person, Depends(current_person("owner"))],
    db: Annotated[Session, Depends(get_session)],
) -> AdminChanged:
    """The OWNER replaces the ADMIN of another church with one of its members, in one
    transaction: the successor becomes the ADMIN directly (keeping any group they lead), the old
    ADMIN stays as a provider or a searcher, set by the OWNER, and nobody is flagged. If the old
    ADMIN leads a home group it passes to `group_successor_id`, or they keep leading it as a
    VERIFIER when they are alone in it. The OWNER's own church changes ADMIN only by a handover
    (`409 owner_church`)."""
    church, keeps_group = succession.replace_admin(
        db, owner, church_id, body.successor_id, body.former_admin_status, body.group_successor_id
    )
    succession.end_commit(db)
    admin = db.get(Person, church.admin_id)
    return AdminChanged(
        church=IdName(id=church.id, name=church.name),
        admin=IdName(id=church.admin_id, name=(admin.full_name if admin else "") or ""),
        former_admin_keeps_leading=keeps_group,
    )
