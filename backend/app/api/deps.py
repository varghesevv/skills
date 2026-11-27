from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal, TokenError, decode_access_token
from app.models.church import Person
from app.models.enums import STATUS_RANK, Status

_bearer = HTTPBearer(auto_error=False)


def client_address(request: Request) -> str:
    """The caller's address for rate limits. Behind the reverse proxy uvicorn runs with
    `--proxy-headers`, trusting the forwarded address from the proxy only (docs/specification/
    09-infrastructure.md), so this is the real client, as for login throttling."""
    return request.client.host if request.client else "unknown"


def _decode(credentials: HTTPAuthorizationCredentials | None, settings: Settings) -> Principal:
    challenge = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise ApiError(401, "not_authenticated", "Authentication required", headers=challenge)
    try:
        return decode_access_token(credentials.credentials, secret=settings.require_jwt_secret())
    except TokenError:
        raise ApiError(
            401, "invalid_token", "The access token is invalid or expired", headers=challenge
        ) from None


def _load_person(
    db: Session,
    principal: Principal,
    *,
    allow_revoked: bool,
    allow_password_change: bool = False,
) -> Person:
    """The person behind a token, read from the database on every request (ADR-0017).

    The token carries no status, so a status change takes effect on the next request. A person
    who still has a temporary password (`must_change_password`) is refused everywhere except the
    few endpoints that set `allow_password_change`: `GET /me` and changing the password.
    """
    person = db.get(Person, principal.user_id)
    if person is None or person.closed_at is not None:
        raise ApiError(
            401,
            "invalid_token",
            "The account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if person.status == "revoked" and not allow_revoked:
        raise ApiError(403, "account_revoked", "This account has been revoked")
    if person.must_change_password and not allow_password_change:
        raise ApiError(403, "password_change_required", "Choose a new password before you continue")
    return person


def get_principal_even_if_revoked(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_session),
) -> Principal:
    """Like `get_principal`, but a revoked person is let through, to see why they have no access.

    Only for the few endpoints a revoked person may use (`/me`). A closed account is still a 401.
    """
    principal = _decode(credentials, settings)
    _load_person(db, principal, allow_revoked=True, allow_password_change=True)
    return principal


def person_changing_password(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_session),
) -> Person:
    """The caller, for changing their own password: also a person who must change a temporary
    one. A revoked person keeps their account and may change it too; a closed account is a 401."""
    principal = _decode(credentials, settings)
    return _load_person(db, principal, allow_revoked=True, allow_password_change=True)


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_session),
) -> Principal:
    """The caller, from a valid `Authorization: Bearer <access token>` header.

    The person is checked in the database too: a closed account is a 401 and a revoked one a 403,
    whatever the endpoint.
    """
    principal = _decode(credentials, settings)
    _load_person(db, principal, allow_revoked=False)
    return principal


def current_person(
    min_status: Status = "pending", *, allow_revoked: bool = False
) -> Callable[..., Person]:
    """Dependency that returns the calling person, checked against the database.

    `min_status` is the lowest status allowed ("at least X"); a lower one is `403 not_admitted`.
    Only the few endpoints a revoked person may still use set `allow_revoked`.
    """

    if min_status not in STATUS_RANK:  # a typo in a route fails at start-up, not per request
        raise ValueError(f"unknown status {min_status!r}")

    def check(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        settings: Settings = Depends(get_settings),
        db: Session = Depends(get_session),
    ) -> Person:
        principal = _decode(credentials, settings)
        person = _load_person(db, principal, allow_revoked=allow_revoked)
        if person.status != "revoked" and STATUS_RANK[person.status] < STATUS_RANK[min_status]:
            raise ApiError(403, "not_admitted", "This is not available to you yet")
        return person

    return check
