from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import client_address
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.signup import SignupRequest, SignupResponse
from app.services import auth
from app.services import signup as signup_service
from app.services.rate_limit import signup_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    request: Request,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SignupResponse:
    """Public. Creates a PENDING person in the chosen home group and tells its leader."""
    signup_limiter.check(client_address(request), settings.signup_max_per_hour)
    person = signup_service.sign_up(
        db,
        settings,
        full_name=body.full_name,
        email=body.email,
        mobile_number=body.mobile_number,
        password=body.password.get_secret_value(),
        requested_status=body.requested_status,
        home_group_id=body.home_group_id,
        invitation_token=body.invitation_token,
    )
    return SignupResponse(id=person.id)


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
    auth.forgot_password(db, settings, email=body.email)
    # Same answer whether or not the email exists.
    return {"status": "accepted"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_session)) -> Response:
    auth.reset_password(db, token=body.token, new_password=body.new_password.get_secret_value())
    return Response(status_code=status.HTTP_204_NO_CONTENT)
