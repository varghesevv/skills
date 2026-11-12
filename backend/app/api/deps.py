from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal, TokenError, decode_access_token
from app.models.church import Person
from app.models.enums import STATUS_RANK

_bearer = HTTPBearer(auto_error=False)


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


def _load_person(db: Session, principal: Principal, *, allow_revoked: bool) -> Person:
    """The person behind a token, read from the database on every request (ADR-0017).

    The token carries no status, so a status change takes effect on the next request.
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
    return person


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_session),
) -> Principal:
    """The caller, from a valid `Authorization: Bearer <access token>` header.

    For a person the account is checked in the database too: a closed account is a 401 and a
    revoked one a 403, whatever the endpoint.
    """
    principal = _decode(credentials, settings)
    if principal.user_type == "person":
        _load_person(db, principal, allow_revoked=False)
    return principal


def current_person(
    min_status: str = "pending", *, allow_revoked: bool = False
) -> Callable[..., Person]:
    """Dependency that returns the calling person, checked against the database.

    `min_status` is the lowest status allowed ("at least X"); a lower one is `403 not_admitted`.
    Only the few endpoints a revoked person may still use set `allow_revoked`.
    """

    def check(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        settings: Settings = Depends(get_settings),
        db: Session = Depends(get_session),
    ) -> Person:
        principal = _decode(credentials, settings)
        if principal.user_type != "person":
            raise ApiError(403, "forbidden", "You are not allowed to do this")
        person = _load_person(db, principal, allow_revoked=allow_revoked)
        if person.status != "revoked" and STATUS_RANK[person.status] < STATUS_RANK[min_status]:
            raise ApiError(403, "not_admitted", "This is not available to you yet")
        return person

    return check


def require_roles(*roles: str) -> Callable[[Principal], Principal]:
    """Dependency that allows only the given user types (403 for everyone else)."""

    def check(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.user_type not in roles:
            raise ApiError(403, "forbidden", "You are not allowed to do this")
        return principal

    return check
