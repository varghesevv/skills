import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import (
    Principal,
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)

SECRET = secrets.token_hex(32)


def test_password_hash_is_argon2id_and_verifies() -> None:
    password = secrets.token_urlsafe(12)
    hashed = hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert password not in hashed
    assert verify_password(hashed, password)
    assert not verify_password(hashed, secrets.token_urlsafe(12))
    assert not verify_password("not-a-hash", password)


def test_access_token_round_trip() -> None:
    principal = Principal("freelancer", uuid.uuid4())
    token, expires_in = create_access_token(principal, secret=SECRET, lifetime_minutes=15)
    assert expires_in == 900
    assert decode_access_token(token, secret=SECRET) == principal


def test_access_token_rejects_wrong_key_expiry_and_tampering() -> None:
    principal = Principal("admin", uuid.uuid4())
    token, _ = create_access_token(principal, secret=SECRET, lifetime_minutes=15)
    with pytest.raises(TokenError):
        decode_access_token(token, secret=secrets.token_hex(32))
    old = datetime.now(UTC) - timedelta(hours=1)
    expired, _ = create_access_token(principal, secret=SECRET, lifetime_minutes=15, now=old)
    with pytest.raises(TokenError):
        decode_access_token(expired, secret=SECRET)
    with pytest.raises(TokenError):
        decode_access_token(token[:-2] + "xx", secret=SECRET)


def test_unsigned_token_is_rejected() -> None:
    forged = jwt.encode({"sub": str(uuid.uuid4()), "role": "admin"}, key="", algorithm="none")
    with pytest.raises(TokenError):
        decode_access_token(forged, secret=SECRET)


def test_opaque_tokens_are_random_and_hashed() -> None:
    first, second = new_opaque_token(), new_opaque_token()
    assert first != second
    assert hash_token(first) != first
    assert hash_token(first) == hash_token(first)
