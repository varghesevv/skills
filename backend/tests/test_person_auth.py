"""Authentication of the church trust model: one login for every person (ADR-0017).

The token identifies the person only. The status is read from the database on every request, so
a change of status takes effect on the next request without a new token.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.security import hash_password
from app.models import LoginHistory, Person, RefreshToken
from app.models.church import Person as PersonModel
from tests.api_helpers import API, signup
from tests.trust_helpers import World

pytestmark = pytest.mark.db


Anyone = Annotated[PersonModel, Depends(current_person("pending"))]
Searchers = Annotated[PersonModel, Depends(current_person("searcher"))]
RevokedOk = Annotated[PersonModel, Depends(current_person("pending", allow_revoked=True))]


class Member:
    def __init__(self, person: Person, password: str) -> None:
        self.person = person
        self.password = password
        self.email = str(person.email)


def add_member(world: World, status: str, **extra: object) -> Member:
    password = secrets.token_urlsafe(16)
    person = world.add_person(status, password_hash=hash_password(password), **extra)
    if status == "verifier":
        world.add_group(person, f"Group of {person.email}")
    return Member(person, password)


def login(client: TestClient, member: Member, **body: object) -> dict[str, str]:
    response = client.post(
        f"{API}/auth/login", json={"email": member.email, "password": member.password, **body}
    )
    assert response.status_code == 200, response.text
    token: dict[str, str] = response.json()
    return token


def bearer(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture
def guarded(client: TestClient, session: Session) -> TestClient:
    """The client, with test routes that use the dependency every new endpoint will use."""
    from app.main import app

    router = APIRouter()

    @router.get("/test/anyone")
    def anyone(person: Anyone) -> dict[str, str]:
        return {"status": person.status}

    @router.get("/test/searchers")
    def searchers(person: Searchers) -> dict[str, str]:
        return {"status": person.status}

    @router.get("/test/revoked-ok")
    def revoked_ok(person: RevokedOk) -> dict[str, str]:
        return {"status": person.status}

    app.include_router(router, prefix=API)
    yield_client = client
    try:
        yield yield_client
    finally:
        app.router.routes[:] = [
            r
            for r in app.router.routes
            if not str(getattr(r, "path", "")).startswith(f"{API}/test/")
        ]


# ---- login -------------------------------------------------------------------------------------


def test_one_login_for_every_status(client: TestClient, world: World) -> None:
    for status in ("pending", "searcher", "provider"):
        member = add_member(world, status)
        tokens = login(client, member)
        assert tokens["token_type"] == "bearer"
        assert tokens["refresh_token"]


def test_login_needs_no_user_type_and_old_accounts_still_log_in(
    client: TestClient, session: Session, world: World
) -> None:
    host = signup(client, session, "workhost", "old-host@example.com")
    assert host.headers  # the older login with user_type still works
    member = add_member(world, "searcher")
    assert (
        client.post(
            f"{API}/auth/login", json={"email": member.email, "password": member.password}
        ).status_code
        == 200
    )


def test_the_access_token_carries_no_status(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    token = login(client, member)["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] == str(member.person.id)
    assert not {"status", "church_id", "home_group_id"} & set(claims)
    assert "provider" not in claims.values()


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    wrong = client.post(f"{API}/auth/login", json={"email": member.email, "password": "x" * 12})
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "x" * 12}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_a_closed_account_cannot_log_in(client: TestClient, session: Session, world: World) -> None:
    member = add_member(world, "searcher")
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    session.flush()
    response = client.post(
        f"{API}/auth/login", json={"email": member.email, "password": member.password}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_a_revoked_person_can_log_in(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    assert login(client, member)["access_token"]


def test_logins_are_recorded_for_people(client: TestClient, session: Session, world: World) -> None:
    member = add_member(world, "searcher")
    client.post(f"{API}/auth/login", json={"email": member.email, "password": "x" * 12})
    login(client, member)
    rows = session.scalars(
        select(LoginHistory).where(LoginHistory.login_email == member.email)
    ).all()
    assert [(r.user_type, r.succeeded) for r in rows] == [("person", False), ("person", True)]
    assert all(r.user_id == member.person.id for r in rows)
    assert member.person.last_login_at is not None


def test_failed_logins_are_throttled(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    for _ in range(5):
        client.post(f"{API}/auth/login", json={"email": member.email, "password": "x" * 12})
    response = client.post(
        f"{API}/auth/login", json={"email": member.email, "password": member.password}
    )
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


# ---- refresh, logout, password reset ---------------------------------------------------------


def test_refresh_rotates_and_reuse_ends_every_session(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "searcher")
    first = login(client, member)
    second = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    # The rotated token comes back: assume theft and end every session.
    again = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert again.status_code == 401
    after = client.post(
        f"{API}/auth/refresh", json={"refresh_token": second.json()["refresh_token"]}
    )
    assert after.status_code == 401
    rows = session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == member.person.id)
    ).all()
    assert rows and all(r.revoked_at is not None and r.user_type == "person" for r in rows)


def test_refresh_stops_for_a_closed_account(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    session.flush()
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_a_revoked_person_keeps_the_session(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200


def test_logout_revokes_the_refresh_token(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    assert (
        client.post(
            f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_password_reset_for_a_person(
    client: TestClient, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    member = add_member(world, "searcher")
    with caplog.at_level("INFO"):
        response = client.post(f"{API}/auth/forgot-password", json={"email": member.email})
    assert response.status_code == 202
    link = next(r.reset_link for r in caplog.records if hasattr(r, "reset_link"))
    token = link.split("token=")[1]
    old_session = login(client, member)
    new_password = secrets.token_urlsafe(16)
    assert (
        client.post(
            f"{API}/auth/reset-password", json={"token": token, "new_password": new_password}
        ).status_code
        == 204
    )
    # The old password and the old sessions are dead; the new password works.
    assert (
        client.post(
            f"{API}/auth/login", json={"email": member.email, "password": member.password}
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{API}/auth/refresh", json={"refresh_token": old_session["refresh_token"]}
        ).status_code
        == 401
    )
    member.password = new_password
    assert login(client, member)["access_token"]


def test_a_reset_link_does_not_work_after_the_account_is_closed(
    client: TestClient, session: Session, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    member = add_member(world, "searcher")
    with caplog.at_level("INFO"):
        client.post(f"{API}/auth/forgot-password", json={"email": member.email})
    token = next(r.reset_link for r in caplog.records if hasattr(r, "reset_link")).split("token=")[
        1
    ]
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    session.flush()
    response = client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": secrets.token_urlsafe(16)},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_reset_token"


def test_forgot_password_answers_alike_for_unknown_emails(client: TestClient) -> None:
    response = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 202


# ---- the live check on every request ----------------------------------------------------------


def test_status_is_read_from_the_database_on_every_request(
    guarded: TestClient, world: World
) -> None:
    member = add_member(world, "pending")
    headers = bearer(login(guarded, member))
    assert guarded.get(f"{API}/test/anyone", headers=headers).json() == {"status": "pending"}
    denied = guarded.get(f"{API}/test/searchers", headers=headers)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "not_admitted")
    # Admitted: the same token now passes, with no new login.
    member.person.status = "searcher"
    world.session.flush()
    assert guarded.get(f"{API}/test/searchers", headers=headers).json() == {"status": "searcher"}


def test_revoking_takes_effect_on_the_next_request(guarded: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    headers = bearer(login(guarded, member))
    assert guarded.get(f"{API}/test/searchers", headers=headers).status_code == 200
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = guarded.get(f"{API}/test/searchers", headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")
    # The few endpoints a revoked person may use still answer.
    assert guarded.get(f"{API}/test/revoked-ok", headers=headers).json() == {"status": "revoked"}


def test_a_closed_account_is_refused_with_a_valid_token(guarded: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(guarded, member))
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    world.session.flush()
    assert guarded.get(f"{API}/test/anyone", headers=headers).status_code == 401


def test_other_endpoints_refuse_revoked_people_too(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    assert client.get(f"{API}/labels", headers=headers).status_code == 200
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.get(f"{API}/labels", headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")


def test_old_account_tokens_do_not_open_person_endpoints(
    guarded: TestClient, session: Session
) -> None:
    host = signup(guarded, session, "workhost", "old-host2@example.com")
    assert guarded.get(f"{API}/test/anyone", headers=host.headers).status_code == 403


def test_a_person_token_does_not_open_old_role_endpoints(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    headers = bearer(login(client, member))
    for path in ("/freelancers/me", "/workhosts/me", "/organisations/me", "/admin/organisations"):
        assert client.get(f"{API}{path}", headers=headers).status_code == 403, path


def test_an_expired_or_forged_token_is_refused(guarded: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    forged = jwt.encode(
        {
            "sub": str(member.person.id),
            "role": "person",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        secrets.token_hex(32),
        algorithm="HS256",
    )
    response = guarded.get(f"{API}/test/anyone", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
    assert guarded.get(f"{API}/test/anyone").status_code == 401


def test_an_unknown_status_in_a_route_fails_at_start_up() -> None:
    with pytest.raises(ValueError):
        current_person("kng")  # type: ignore[arg-type]


def test_an_account_without_a_password_hash_costs_the_same_as_an_unknown_email(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The schema forbids an open account without a hash, so the branch is reached with a stub."""
    import app.services.auth as auth_service

    member = add_member(world, "searcher")
    stub = type("Stub", (), {"id": member.person.id, "password_hash": None})()
    monkeypatch.setattr(auth_service, "get_by_email", lambda *_args, **_kwargs: stub)
    calls: list[int] = []
    monkeypatch.setattr(auth_service, "verify_dummy", lambda _password: calls.append(1))
    response = client.post(f"{API}/auth/login", json={"email": member.email, "password": "x" * 12})
    assert response.status_code == 401
    assert calls == [1]
