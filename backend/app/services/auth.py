"""Login, token refresh, logout and password reset.

Rules: wrong credentials always look the same (no hint whether the email exists), every login
attempt is recorded, and tokens are stored only as hashes. Secrets are never logged; the one
deliberate exception is the password reset link (see forgot_password).
"""

import ipaddress
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import (
    Principal,
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    password_needs_rehash,
    verify_dummy,
    verify_password,
)
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from app.models.users import Organisation
from app.schemas.auth import TokenResponse
from app.services.accounts import Account, get_by_email, get_by_id

logger = logging.getLogger(__name__)

def _invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Invalid email or password")


def clean_ip(value: str | None) -> str | None:
    """Return the value if it is a valid IP address (the column is INET), otherwise None."""
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _ip_filter(ip: str | None) -> ColumnElement[bool]:
    column = LoginHistory.ip_address
    return column.is_(None) if ip is None else column == ip


def _record(
    db: Session,
    *,
    user_type: str,
    user_id: uuid.UUID | None,
    email: str,
    succeeded: bool,
    ip: str | None,
    user_agent: str | None,
) -> None:
    db.add(
        LoginHistory(
            user_type=user_type,
            user_id=user_id,
            login_email=email,
            succeeded=succeeded,
            login_time=datetime.now(UTC),
            ip_address=ip,
            user_agent=user_agent[:500] if user_agent else None,
        )
    )


def _check_throttle(
    db: Session, settings: Settings, *, user_type: str, email: str, ip: str | None, now: datetime
) -> None:
    """Too many recent failures for this email and IP: answer 429 before checking the password."""
    window = timedelta(minutes=settings.login_window_minutes)
    last_success = db.scalar(
        select(func.max(LoginHistory.login_time)).where(
            LoginHistory.login_email == email,
            LoginHistory.user_type == user_type,
            _ip_filter(ip),
            LoginHistory.succeeded.is_(True),
        )
    )
    since = now - window
    if last_success is not None and last_success > since:
        since = last_success
    failures = db.scalars(
        select(LoginHistory.login_time)
        .where(
            LoginHistory.login_email == email,
            LoginHistory.user_type == user_type,
            _ip_filter(ip),
            LoginHistory.succeeded.is_(False),
            LoginHistory.login_time > since,
        )
        .order_by(LoginHistory.login_time)
    ).all()
    if len(failures) >= settings.login_max_failures:
        wait = math.ceil((failures[0] + window - now).total_seconds())
        raise ApiError(
            429,
            "too_many_attempts",
            "Too many failed attempts. Try again later.",
            headers={"Retry-After": str(max(wait, 1))},
        )


def _issue_refresh_token(
    db: Session, settings: Settings, principal: Principal, now: datetime
) -> tuple[str, RefreshToken]:
    token = new_opaque_token()
    row = RefreshToken(
        id=uuid.uuid4(),
        user_type=principal.user_type,
        user_id=principal.user_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    db.add(row)
    return token, row


def _token_response(
    db: Session, settings: Settings, principal: Principal, now: datetime
) -> tuple[TokenResponse, RefreshToken]:
    access, expires_in = create_access_token(
        principal,
        secret=settings.require_jwt_secret(),
        lifetime_minutes=settings.access_token_minutes,
        now=now,
    )
    refresh, row = _issue_refresh_token(db, settings, principal, now)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in), row


def _can_log_in(account: Account) -> ApiError | None:
    if isinstance(account, Organisation) and account.approval_status != "approved":
        if account.approval_status == "rejected":
            return ApiError(403, "organisation_rejected", "This organisation was not approved")
        return ApiError(
            403, "organisation_pending", "This organisation is waiting for admin approval"
        )
    return None


def login(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    user_type: str,
    ip: str | None,
    user_agent: str | None,
) -> TokenResponse:
    now = datetime.now(UTC)
    ip = clean_ip(ip)
    _check_throttle(db, settings, user_type=user_type, email=email, ip=ip, now=now)
    account = get_by_email(db, user_type, email)

    def record(user_id: uuid.UUID | None, *, succeeded: bool) -> None:
        _record(
            db,
            user_type=user_type,
            user_id=user_id,
            email=email,
            succeeded=succeeded,
            ip=ip,
            user_agent=user_agent,
        )

    if account is None or not verify_password(account.password_hash, password):
        if account is None:
            verify_dummy(password)  # same cost as a real check
        record(account.id if account else None, succeeded=False)
        db.commit()
        raise _invalid_credentials()

    blocked = _can_log_in(account)
    if blocked is not None:
        record(account.id, succeeded=False)
        db.commit()
        raise blocked

    if password_needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)
    account.last_login_at = now
    record(account.id, succeeded=True)
    tokens, _ = _token_response(db, settings, Principal(user_type, account.id), now)
    db.commit()
    return tokens


def _revoke_all(db: Session, user_type: str, user_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_type == user_type,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def refresh(db: Session, settings: Settings, *, refresh_token: str) -> TokenResponse:
    """Exchange a refresh token for new tokens. The old token stops working (rotation)."""
    now = datetime.now(UTC)
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    invalid = ApiError(401, "invalid_refresh_token", "The refresh token is not valid")
    if row is None:
        raise invalid
    if row.revoked_at is not None:
        # A rotated or logged-out token came back: assume it was stolen, end every session.
        _revoke_all(db, row.user_type, row.user_id, now)
        db.commit()
        raise invalid
    if row.expires_at <= now:
        raise invalid
    account = get_by_id(db, row.user_type, row.user_id)
    if account is None or _can_log_in(account) is not None:
        raise invalid
    tokens, new_row = _token_response(db, settings, Principal(row.user_type, row.user_id), now)
    row.revoked_at = now
    row.replaced_by_id = new_row.id
    db.commit()
    return tokens


def logout(db: Session, *, refresh_token: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()


def forgot_password(db: Session, settings: Settings, *, email: str, user_type: str) -> None:
    """Create a reset token and log the reset link. Behaves the same for unknown emails."""
    account = get_by_email(db, user_type, email)
    if account is None:
        return
    now = datetime.now(UTC)
    token = new_opaque_token()
    db.add(
        PasswordResetToken(
            user_type=user_type,
            user_id=account.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=settings.reset_token_minutes),
        )
    )
    db.commit()
    link = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"
    # The reset link is the one secret that is deliberately logged: there is no email delivery
    # yet. Replace this with email sending when SMTP is added (open question Q7).
    logger.info(
        "Password reset link for %s (%s), valid %s minutes: %s",
        email,
        user_type,
        settings.reset_token_minutes,
        link,
        extra={"reset_link": link},
    )


def reset_password(db: Session, *, token: str, new_password: str) -> None:
    now = datetime.now(UTC)
    row = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(token))
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ApiError(400, "invalid_reset_token", "The reset link is invalid or has expired")
    account = get_by_id(db, row.user_type, row.user_id)
    if account is None:
        raise ApiError(400, "invalid_reset_token", "The reset link is invalid or has expired")
    account.password_hash = hash_password(new_password)
    # Use up every outstanding reset link for this user and end all sessions.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_type == row.user_type,
            PasswordResetToken.user_id == row.user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    _revoke_all(db, row.user_type, row.user_id, now)
    db.commit()
