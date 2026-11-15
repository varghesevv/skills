"""Login, refresh, logout and password reset over HTTP, for people (ADR-0017)."""

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from tests.trust_helpers import World

API = "/api/v1"

pytestmark = pytest.mark.db


def new_password() -> str:
    return secrets.token_urlsafe(16)


def register(session: Session, email: str, password: str) -> None:
    """A person who can log in (a SEARCHER of the first church)."""
    world = World(session)
    world.add_person("searcher", email=email, password_hash=hash_password(password))
    session.flush()


def login(client: TestClient, email: str, password: str):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---- login --------------------------------------------------------------------------------


def test_login_returns_tokens_and_me_works(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "f@example.com", password)
    response = login(client, "F@Example.com", password)
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == get_settings().access_token_minutes * 60

    me = client.get(f"{API}/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "f@example.com"
    assert me.json()["user_type"] == "person"

    history = session.scalars(select(LoginHistory)).all()
    assert [(h.login_email, h.succeeded) for h in history] == [("f@example.com", True)]
    assert str(history[0].ip_address) == "203.0.113.7"


def test_wrong_password_and_unknown_email_look_the_same(
    client: TestClient, session: Session
) -> None:
    password = new_password()
    register(session, "known@example.com", password)
    wrong = login(client, "known@example.com", new_password())
    unknown = login(client, "nobody@example.com", new_password())
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_failed_logins_are_throttled_then_429_with_retry_after(
    client: TestClient, session: Session
) -> None:
    password = new_password()
    register(session, "limit@example.com", password)
    for _ in range(get_settings().login_max_failures):
        assert login(client, "limit@example.com", new_password()).status_code == 401
    blocked = login(client, "limit@example.com", password)  # even the right password
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.json()["error"]["code"] == "too_many_attempts"


def test_throttle_counts_per_email(client: TestClient, session: Session) -> None:
    for _ in range(get_settings().login_max_failures):
        login(client, "a@example.com", new_password())
    password = new_password()
    register(session, "b@example.com", password)
    assert login(client, "b@example.com", password).status_code == 200


def test_failures_of_an_older_account_do_not_count_against_a_person(
    client: TestClient, session: Session
) -> None:
    register(session, "mixed@example.com", (password := new_password()))
    for _ in range(get_settings().login_max_failures):
        session.add(
            LoginHistory(
                user_type="workhost",
                login_email="mixed@example.com",
                succeeded=False,
                login_time=datetime.now(UTC),
                ip_address="203.0.113.7",  # the address the test client logs in from
            )
        )
    session.flush()
    assert login(client, "mixed@example.com", password).status_code == 200


def test_failures_older_than_the_window_do_not_count(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "old@example.com", password)
    for _ in range(get_settings().login_max_failures):
        login(client, "old@example.com", new_password())
    old = datetime.now(UTC) - timedelta(minutes=get_settings().login_window_minutes + 1)
    session.execute(update(LoginHistory).values(login_time=old))
    assert login(client, "old@example.com", password).status_code == 200


def test_me_rejects_missing_and_bad_tokens(client: TestClient) -> None:
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/me", headers=bearer("not-a-token")).status_code == 401


# ---- refresh and logout -------------------------------------------------------------------


def test_refresh_rotates_and_old_token_is_dead(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "r@example.com", password)
    first = login(client, "r@example.com", password).json()
    second = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    assert client.get(f"{API}/me", headers=bearer(second.json()["access_token"])).status_code == 200

    # Re-using the old token is treated as theft: it fails and kills the new one too.
    replay = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    newer = {"refresh_token": second.json()["refresh_token"]}
    after = client.post(f"{API}/auth/refresh", json=newer)
    assert after.status_code == 401
    assert all(t.revoked_at is not None for t in session.scalars(select(RefreshToken)).all())


def test_refresh_tokens_are_stored_only_as_hashes(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "h@example.com", password)
    tokens = login(client, "h@example.com", password).json()
    stored = session.scalars(select(RefreshToken.token_hash)).all()
    assert tokens["refresh_token"] not in stored
    assert len(stored) == 1


def test_logout_revokes_the_refresh_token(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "l@example.com", password)
    tokens = login(client, "l@example.com", password).json()
    body = {"refresh_token": tokens["refresh_token"]}
    assert client.post(f"{API}/auth/logout", json=body).status_code == 204
    assert client.post(f"{API}/auth/refresh", json=body).status_code == 401


def test_expired_refresh_token_is_rejected(client: TestClient, session: Session) -> None:
    password = new_password()
    register(session, "e@example.com", password)
    tokens = login(client, "e@example.com", password).json()
    session.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(days=1)))
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


# ---- password reset -----------------------------------------------------------------------


def reset_token_from_log(text: str) -> str:
    match = re.search(r"reset-password\?token=([A-Za-z0-9_-]+)", text)
    assert match, "the reset link was not logged"
    return match.group(1)


def test_password_reset_flow(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    old, new = new_password(), new_password()
    register(session, "reset@example.com", old)
    session_tokens = login(client, "reset@example.com", old).json()

    with caplog.at_level(logging.INFO):
        response = client.post(
            f"{API}/auth/forgot-password",
            json={"email": "reset@example.com"},
        )
    assert response.status_code == 202
    token = reset_token_from_log(caplog.text)
    assert old not in caplog.text
    stored = session.scalars(select(PasswordResetToken.token_hash)).all()
    assert token not in stored  # only the hash is stored

    done = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new})
    assert done.status_code == 204
    assert login(client, "reset@example.com", old).status_code == 401
    assert login(client, "reset@example.com", new).status_code == 200
    # Every session was ended and the link is single use.
    refresh = client.post(
        f"{API}/auth/refresh", json={"refresh_token": session_tokens["refresh_token"]}
    )
    assert refresh.status_code == 401
    again = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new})
    assert again.status_code == 400


def test_forgot_password_gives_the_same_answer_for_unknown_email(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        response = client.post(
            f"{API}/auth/forgot-password",
            json={"email": "ghost@example.com"},
        )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert "reset-password" not in caplog.text


def test_expired_or_unknown_reset_token_is_rejected(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    register(session, "exp@example.com", new_password())
    with caplog.at_level(logging.INFO):
        client.post(
            f"{API}/auth/forgot-password",
            json={"email": "exp@example.com"},
        )
    token = reset_token_from_log(caplog.text)
    past = datetime.now(UTC) - timedelta(minutes=1)
    session.execute(update(PasswordResetToken).values(expires_at=past))
    body = {"token": token, "new_password": new_password()}
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 400
    body["token"] = secrets.token_urlsafe(32)
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 400


def test_nothing_secret_is_logged_during_login(
    client: TestClient, caplog: pytest.LogCaptureFixture, session: Session
) -> None:
    password = new_password()
    register(session, "quiet@example.com", password)
    with caplog.at_level(logging.DEBUG):
        tokens = login(client, "quiet@example.com", password).json()
        login(client, "quiet@example.com", new_password())
    assert password not in caplog.text
    assert tokens["access_token"] not in caplog.text
    assert tokens["refresh_token"] not in caplog.text
