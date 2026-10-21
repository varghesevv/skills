from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_principal
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.users import Organisation
from app.schemas.auth import MeResponse
from app.services.accounts import get_by_id

router = APIRouter(tags=["me"])


@router.get("/me")
def me(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_session)
) -> MeResponse:
    account = get_by_id(db, principal.user_type, principal.user_id)
    if account is None:
        raise ApiError(401, "invalid_token", "The account no longer exists")
    org = account if isinstance(account, Organisation) else None
    return MeResponse(
        id=account.id,
        user_type=principal.user_type,  # type: ignore[arg-type]
        email=account.user_email,
        mobile_number=account.mobile_number,
        org_name=org.org_name if org else None,
        approval_status=org.approval_status if org else None,
        created_at=account.created_at,
    )
