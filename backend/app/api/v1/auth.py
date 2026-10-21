from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.users import Organisation
from app.schemas.auth import (
    FreelancerRegister,
    ForgotPasswordRequest,
    LoginRequest,
    OrganisationRegister,
    RefreshRequest,
    RegisterBase,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    WorkHostRegister,
)
from app.services import accounts, auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _register(
    db: Session, user_type: str, body: RegisterBase, **extra: Any
) -> RegisterResponse:
    account = accounts.create_account(
        db,
        user_type,
        email=body.email,
        mobile_number=body.mobile_number,
        password=body.password.get_secret_value(),
        **extra,
    )
    return RegisterResponse(
        id=account.id,
        user_type=user_type,  # type: ignore[arg-type]
        email=account.user_email,
        approval_status=account.approval_status if isinstance(account, Organisation) else None,
    )


@router.post("/register/freelancer", status_code=status.HTTP_201_CREATED)
def register_freelancer(
    body: FreelancerRegister, db: Session = Depends(get_session)
) -> RegisterResponse:
    return _register(
        db,
        "freelancer",
        body,
        nationality=body.nationality,
        primary_language=body.primary_language,
        whatsapp_availability=body.whatsapp_availability,
    )


@router.post("/register/workhost", status_code=status.HTTP_201_CREATED)
def register_workhost(body: WorkHostRegister, db: Session = Depends(get_session)) -> RegisterResponse:
    return _register(db, "workhost", body)


@router.post("/register/organisation", status_code=status.HTTP_201_CREATED)
def register_organisation(
    body: OrganisationRegister, db: Session = Depends(get_session)
) -> RegisterResponse:
    return _register(db, "organisation", body, org_name=body.org_name)


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    return auth.login(
        db,
        settings,
        email=body.email,
        password=body.password.get_secret_value(),
        user_type=body.user_type,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh")
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    return auth.refresh(db, settings, refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: Session = Depends(get_session)) -> Response:
    auth.logout(db, refresh_token=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    auth.forgot_password(db, settings, email=body.email, user_type=body.user_type)
    # Same answer whether or not the email exists.
    return {"status": "accepted"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_session)) -> Response:
    auth.reset_password(
        db, token=body.token, new_password=body.new_password.get_secret_value()
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
