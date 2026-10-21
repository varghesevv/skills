from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import Principal, TokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    """The caller, from a valid `Authorization: Bearer <access token>` header."""
    challenge = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise ApiError(401, "not_authenticated", "Authentication required", headers=challenge)
    try:
        return decode_access_token(credentials.credentials, secret=settings.require_jwt_secret())
    except TokenError:
        raise ApiError(
            401, "invalid_token", "The access token is invalid or expired", headers=challenge
        ) from None


def require_roles(*roles: str) -> Callable[[Principal], Principal]:
    """Dependency that allows only the given user types (403 for everyone else)."""

    def check(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.user_type not in roles:
            raise ApiError(403, "forbidden", "You are not allowed to do this")
        return principal

    return check
