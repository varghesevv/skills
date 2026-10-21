"""Password hashing, access tokens (JWT) and opaque tokens. Nothing here logs or returns secrets."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()  # argon2id with the library's recommended parameters
# Verified against when an email is unknown, so unknown and known emails take similar time.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


class TokenError(Exception):
    """An access token is missing, malformed, expired or has a bad signature."""


@dataclass(frozen=True)
class Principal:
    """Who is calling, taken from a verified access token."""

    user_type: str
    user_id: uuid.UUID


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy(password: str) -> None:
    """Spend the same time as a real check; the result is intentionally ignored."""
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(
    principal: Principal, *, secret: str, lifetime_minutes: int, now: datetime | None = None
) -> tuple[str, int]:
    """Return (token, seconds until it expires)."""
    issued = now or datetime.now(UTC)
    lifetime = timedelta(minutes=lifetime_minutes)
    payload = {
        "sub": str(principal.user_id),
        "role": principal.user_type,
        "iat": issued,
        "exp": issued + lifetime,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM), int(lifetime.total_seconds())


def decode_access_token(token: str, *, secret: str) -> Principal:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]},
        )
        return Principal(user_type=str(claims["role"]), user_id=uuid.UUID(str(claims["sub"])))
    except (jwt.PyJWTError, ValueError):
        raise TokenError("invalid access token") from None


def new_opaque_token() -> str:
    """A random token for refresh and password reset. Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
