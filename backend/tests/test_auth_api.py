"""Registration, login, refresh, logout, password reset and admin approval over HTTP."""

import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from app.models.users import Organisation
from app.services.accounts import create_account

API = "/api/v1"


def new_password() -> str:
    return secrets.token_urlsafe(16)


def register(client: TestClient, user_type: str, email: str, password: str, **extra: object):
    body = {"email": email, "mobile_number": "+971501234567", "password": password, **extra}
    return client.post(f"{API}/auth/register/{user_type}", json=body)


def login(client: TestClient, email: str, password: str, user_type: str = "freelancer"):
    return client.post(
        f"{API}/auth/login", json={"email": email, "password": password, "user_type": user_type}
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---- registration -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user_type", "extra"),
    [("freelancer", {}), ("workhost", {}), ("organisation", {"org_name": "Acme Staffing"})],
)
def test_register_each_user_type(client: TestClient, user_type: str, extra: dict[str, str]) -> None:
    response = register(client, user_type, f"New.{user_type}@Example.com", new_password(), **extra)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == f"new.{user_type}@example.com"  # stored lowercase
    assert "password" not in str(body).lower()
    assert body["approval_status"] == ("pending" if user_type == "organisation" else None)


def test_duplicate_email_is_rejected_but_allowed_for_another_user_type(client: TestClient) -> None:
    password = new_password()
    assert register(client, "freelancer", "dup@example.com", password).status_code == 201
    again = register(client, "freelancer", "dup@example.com", password)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"
    assert register(client, "workhost", "dup@example.com", password).status_code == 201


def test_weak_input_is_rejected_without_echoing_the_password(client: TestClient) -> None:
    short = secrets.token_hex(3)  # 6 characters: below the minimum
    response = register(client, "freelancer", "x@example.com", short)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert short not in response.text
    assert register(client, "freelancer", "not-an-email", new_password()).status_code == 422


def test_organisation_needs_a_name(client: TestClient) -> None:
    assert register(client, "organisation", "o@example.com", new_password()).status_code == 422


# ---- login --------------------------------------------------------------------------------


def test_login_returns_tokens_and_me_works(client: TestClient, session: Session) -> None:
    password = new_password()
    register(client, "freelancer", "f@example.com", password)
    response = login(client, "F@Example.com", password)
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == get_settings().access_token_minutes * 60

    me = client.get(f"{API}/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "f@example.com"
    assert me.json()["user_type"] == "freelancer"

    history = session.scalars(select(LoginHistory)).all()
    assert [(h.login_email, h.succeeded) for h in history] == [("f@example.com", True)]
    assert str(history[0].ip_address) == "203.0.113.7"


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    password = new_password()
    register(client, "freelancer", "known@example.com", password)
    wrong = login(client, "known@example.com", new_password())
    unknown = login(client, "nobody@example.com", new_password())
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_a_user_type_cannot_log_in_as_another(client: TestClient) -> None:
    password = new_password()
    register(client, "freelancer", "typed@example.com", password)
    assert login(client, "typed@example.com", password, "workhost").status_code == 401


def test_failed_logins_are_throttled_then_429_with_retry_after(client: TestClient) -> None:
    password = new_password()
    register(client, "freelancer", "limit@example.com", password)
    for _ in range(get_settings().login_max_failures):
        assert login(client, "limit@example.com", new_password()).status_code == 401
    blocked = login(client, "limit@example.com", password)  # even the right password
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.json()["error"]["code"] == "too_many_attempts"


def test_throttle_counts_per_email(client: TestClient) -> None:
    for _ in range(get_settings().login_max_failures):
        login(client, "a@example.com", new_password())
    password = new_password()
    register(client, "freelancer", "b@example.com", password)
    assert login(client, "b@example.com", password).status_code == 200


def test_failures_older_than_the_window_do_not_count(
    client: TestClient, session: Session
) -> None:
    password = new_password()
    register(client, "freelancer", "old@example.com", password)
    for _ in range(get_settings().login_max_failures):
        login(client, "old@example.com", new_password())
    old = datetime.now(UTC) - timedelta(minutes=get_settings().login_window_minutes + 1)
    session.execute(update(LoginHistory).values(login_time=old))
    assert login(client, "old@example.com", password).status_code == 200


# ---- organisation approval ----------------------------------------------------------------


def test_organisation_cannot_log_in_until_approved(client: TestClient, session: Session) -> None:
    org_password, admin_password = new_password(), new_password()
    registered = register(client, "organisation", "org@example.com", org_password, org_name="Acme")
    org_id = registered.json()["id"]

    pending = login(client, "org@example.com", org_password, "organisation")
    assert pending.status_code == 403
    assert pending.json()["error"]["code"] == "organisation_pending"
    # A wrong password still gives the generic answer, not the status.
    assert login(client, "org@example.com", new_password(), "organisation").status_code == 401

    create_account(
        session, "admin", email="boss@example.com", mobile_number="+971500000000",
        password=admin_password,
    )
    admin_token = login(client, "boss@example.com", admin_password, "admin").json()["access_token"]

    listing = client.get(f"{API}/admin/organisations", headers=bearer(admin_token))
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [org_id]

    approved = client.post(f"{API}/admin/organisations/{org_id}/approve", headers=bearer(admin_token))
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"
    assert session.get(Organisation, uuid.UUID(org_id)).approved_by_admin_id is not None  # type: ignore[union-attr]
    assert login(client, "org@example.com", org_password, "organisation").status_code == 200


def test_rejected_organisation_cannot_log_in(client: TestClient, session: Session) -> None:
    org_password, admin_password = new_password(), new_password()
    org_id = register(
        client, "organisation", "no@example.com", org_password, org_name="Nope"
    ).json()["id"]
    create_account(
        session, "admin", email="boss2@example.com", mobile_number="+971500000000",
        password=admin_password,
    )
    admin_token = login(client, "boss2@example.com", admin_password, "admin").json()["access_token"]
    client.post(f"{API}/admin/organisations/{org_id}/reject", headers=bearer(admin_token))
    response = login(client, "no@example.com", org_password, "organisation")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "organisation_rejected"


def test_admin_endpoints_need_the_admin_role(client: TestClient) -> None:
    assert client.get(f"{API}/admin/organisations").status_code == 401
    password = new_password()
    register(client, "freelancer", "plain@example.com", password)
    token = login(client, "plain@example.com", password).json()["access_token"]
    assert client.get(f"{API}/admin/organisations", headers=bearer(token)).status_code == 403


def test_me_rejects_missing_and_bad_tokens(client: TestClient) -> None:
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/me", headers=bearer("not-a-token")).status_code == 401


# ---- refresh and logout -------------------------------------------------------------------


def test_refresh_rotates_and_old_token_is_dead(client: TestClient, session: Session) -> None:
    password = new_password()
    register(client, "freelancer", "r@example.com", password)
    first = login(client, "r@example.com", password).json()
    second = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    assert client.get(f"{API}/me", headers=bearer(second.json()["access_token"])).status_code == 200

    # Re-using the old token is treated as theft: it fails and kills the new one too.
    replay = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    after = client.post(f"{API}/auth/refresh", json={"refresh_token": second.json()["refresh_token"]})
    assert after.status_code == 401
    assert all(t.revoked_at is not None for t in session.scalars(select(RefreshToken)).all())


def test_refresh_tokens_are_stored_only_as_hashes(client: TestClient, session: Session) -> None:
    password = new_password()
    register(client, "freelancer", "h@example.com", password)
    tokens = login(client, "h@example.com", password).json()
    stored = session.scalars(select(RefreshToken.token_hash)).all()
    assert tokens["refresh_token"] not in stored
    assert len(stored) == 1


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    password = new_password()
    register(client, "freelancer", "l@example.com", password)
    tokens = login(client, "l@example.com", password).json()
    body = {"refresh_token": tokens["refresh_token"]}
    assert client.post(f"{API}/auth/logout", json=body).status_code == 204
    assert client.post(f"{API}/auth/refresh", json=body).status_code == 401


def test_expired_refresh_token_is_rejected(client: TestClient, session: Session) -> None:
    password = new_password()
    register(client, "freelancer", "e@example.com", password)
    tokens = login(client, "e@example.com", password).json()
    session.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(days=1)))
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


# ---- password reset -----------------------------------------------------------------------


def reset_token_from_log(text: str) -> str:
    match = re.search(r"reset-password\?token=([A-Za-z0-9_-]+)", text)
    assert match, "the reset link was not logged"
    return match.group(1)


def test_password_reset_flow(client: TestClient, session: Session, caplog: pytest.LogCaptureFixture) -> None:
    old, new = new_password(), new_password()
    register(client, "freelancer", "reset@example.com", old)
    session_tokens = login(client, "reset@example.com", old).json()

    with caplog.at_level(logging.INFO):
        response = client.post(
            f"{API}/auth/forgot-password",
            json={"email": "reset@example.com", "user_type": "freelancer"},
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
            json={"email": "ghost@example.com", "user_type": "freelancer"},
        )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert "reset-password" not in caplog.text


def test_expired_or_unknown_reset_token_is_rejected(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    register(client, "freelancer", "exp@example.com", new_password())
    with caplog.at_level(logging.INFO):
        client.post(
            f"{API}/auth/forgot-password",
            json={"email": "exp@example.com", "user_type": "freelancer"},
        )
    token = reset_token_from_log(caplog.text)
    session.execute(update(PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    body = {"token": token, "new_password": new_password()}
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 400
    body["token"] = secrets.token_urlsafe(32)
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 400


def test_nothing_secret_is_logged_during_login(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    password = new_password()
    register(client, "freelancer", "quiet@example.com", password)
    with caplog.at_level(logging.DEBUG):
        tokens = login(client, "quiet@example.com", password).json()
        login(client, "quiet@example.com", new_password())
    assert password not in caplog.text
    assert tokens["access_token"] not in caplog.text
    assert tokens["refresh_token"] not in caplog.text

