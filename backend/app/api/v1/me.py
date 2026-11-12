from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import client_address, current_person, get_principal_even_if_revoked
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.church import Person
from app.models.users import Organisation
from app.schemas.auth import MeResponse
from app.schemas.church import CloseAccountRequest, PersonMeResponse, PersonUpdate
from app.schemas.signup import ApplicationUpdate
from app.services import account_closing, directory, signup
from app.services.accounts import get_by_id

router = APIRouter(tags=["me"])

# Every status may change their own name and mobile number, except a revoked person.
Member = Annotated[Person, Depends(current_person("pending"))]


@router.get("/me")
def me(
    principal: Annotated[Principal, Depends(get_principal_even_if_revoked)],
    db: Annotated[Session, Depends(get_session)],
) -> MeResponse | PersonMeResponse:
    """The caller. A person gets the view of the church trust model (a revoked person too, to see
    why they have no access); the older accounts keep their older answer until they are gone."""
    account = get_by_id(db, principal.user_type, principal.user_id)
    if account is None:
        raise ApiError(401, "invalid_token", "The account no longer exists")
    if isinstance(account, Person):
        return directory.person_view(db, account)
    org = account if isinstance(account, Organisation) else None
    return MeResponse(
        id=account.id,
        user_type=principal.user_type,
        email=account.user_email,
        mobile_number=account.mobile_number,
        full_name=getattr(account, "full_name", None),
        org_name=org.org_name if org else None,
        approval_status=org.approval_status if org else None,
        created_at=account.created_at,
    )


@router.put("/me")
def update_me(
    body: PersonUpdate, person: Member, db: Annotated[Session, Depends(get_session)]
) -> PersonMeResponse:
    """Change your own name or mobile number (a field left out keeps its value)."""
    if body.full_name is not None:
        person.full_name = body.full_name
    if body.mobile_number is not None:
        person.mobile_number = body.mobile_number
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "account_exists", "An account with these details already exists"
        ) from None
    return directory.person_view(db, person)


@router.put("/me/application")
def update_application(
    body: ApplicationUpdate, person: Member, db: Annotated[Session, Depends(get_session)]
) -> PersonMeResponse:
    """While pending: choose another home group (even in another church) or another status to
    apply for. Vouches already received still count; a newly chosen leader is notified."""
    signup.change_application(
        db, person, home_group_id=body.home_group_id, requested_status=body.requested_status
    )
    return directory.person_view(db, person)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def close_me(
    body: CloseAccountRequest,
    request: Request,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Close your own account (this is the stores' "delete account"). The password is asked
    again. The record stays, the personal details go. A leader steps down first; the OWNER hands
    over; a revoked person stays on their church's list."""
    account_closing.close_account(
        db,
        settings,
        person,
        body.password.get_secret_value(),
        ip=client_address(request),
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
