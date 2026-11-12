"""A person closes their own account: the record stays, the personal details go."""

import secrets
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    LoginHistory,
    Person,
    RefreshToken,
    StatusChange,
    Vouch,
    VouchLink,
)
from tests.api_helpers import API, signup
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def close(client: TestClient, member: Member, password: str | None = None) -> object:
    headers = bearer(login(client, member))
    return client.request(
        "DELETE", f"{API}/me", headers=headers, json={"password": password or member.password}
    )


@pytest.mark.parametrize("status", ["pending", "searcher", "provider"])
def test_an_applicant_or_member_can_close_their_account(
    client: TestClient, world: World, status: str
) -> None:
    member = add_member(world, status)
    response = close(client, member)
    assert response.status_code == 204  # type: ignore[attr-defined]
    person = member.person
    assert person.closed_at is not None
    assert person.home_group_id is None and person.status == status  # left, not revoked
    assert not any((person.full_name, person.email, person.mobile_number, person.password_hash))
    check_rules(world.session)


def test_the_record_and_its_history_stay(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher", status_set_by_id=world.owner.id)
    world.session.add(
        StatusChange(
            person_id=member.person.id,
            from_status="pending",
            to_status="searcher",
            changed_by_id=world.owner.id,
            kind="admit",
        )
    )
    world.session.flush()
    assert close(client, member).status_code == 204  # type: ignore[attr-defined]
    assert world.session.get(Person, member.person.id) is not None
    changes = world.session.scalars(
        select(StatusChange).where(StatusChange.person_id == member.person.id)
    ).all()
    assert [c.kind for c in changes] == ["admit"]


def test_nobody_they_admitted_is_flagged_and_no_one_is_revoked(
    client: TestClient, world: World
) -> None:
    member = add_member(world, "provider")
    other = world.add_person("searcher", status_set_by_id=member.person.id)
    close(client, member)
    world.session.refresh(other)
    assert other.status == "searcher" and other.flagged_for_recheck is False


def test_they_cannot_log_in_or_use_a_session_afterwards(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    headers = bearer(tokens)
    assert (
        client.request(
            "DELETE", f"{API}/me", headers=headers, json={"password": member.password}
        ).status_code
        == 204
    )
    assert client.get(f"{API}/me", headers=headers).status_code == 401
    assert (
        client.post(
            f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    again = client.post(
        f"{API}/auth/login", json={"email": member.email, "password": member.password}
    )
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "invalid_credentials"


def test_all_their_sessions_links_and_login_traces_go(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "searcher")
    first, second = login(client, member), login(client, member)  # two sessions
    client.post(f"{API}/auth/login", json={"email": member.email, "password": "x" * 12})  # a miss
    session.add(
        VouchLink(
            person_id=member.person.id,
            token_hash=secrets.token_hex(16),
            expires_at=datetime.now(UTC),
        )
    )
    session.flush()
    email = member.email
    assert (
        client.request(
            "DELETE", f"{API}/me", headers=bearer(first), json={"password": member.password}
        ).status_code
        == 204
    )
    tokens = session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == member.person.id)
    ).all()
    assert len(tokens) >= 2 and all(t.revoked_at is not None for t in tokens)
    assert second["refresh_token"]
    assert all(link.revoked_at is not None for link in session.scalars(select(VouchLink)))
    rows = session.scalars(
        select(LoginHistory).where(LoginHistory.user_id == member.person.id)
    ).all()
    assert rows and all(
        (r.login_email, r.ip_address, r.user_agent) == (None, None, None) for r in rows
    )
    assert (
        session.scalars(select(LoginHistory).where(LoginHistory.login_email == email)).all() == []
    )


def test_the_vouches_they_gave_stay_but_stop_counting(client: TestClient, world: World) -> None:
    voucher = add_member(world, "searcher")
    applicant = add_member(world, "pending")
    world.session.add(Vouch(applicant_id=applicant.person.id, voucher_id=voucher.person.id))
    world.session.flush()
    headers = bearer(login(client, applicant))
    assert client.get(f"{API}/me", headers=headers).json()["vouch_count"] == 1
    assert close(client, voucher).status_code == 204  # type: ignore[attr-defined]
    assert world.session.query(Vouch).count() == 1
    assert client.get(f"{API}/me", headers=headers).json()["vouch_count"] == 0


def test_the_address_can_be_used_again_to_sign_up(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    email, mobile = member.email, str(member.person.mobile_number)
    close(client, member)
    again = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Back Again",
            "email": email,
            "mobile_number": mobile,
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(world.group.id),
        },
    )
    assert again.status_code == 201


def test_the_password_is_asked_again(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    response = close(client, member, password=secrets.token_urlsafe(16))
    assert response.status_code == 403  # type: ignore[attr-defined]
    assert response.json()["error"]["code"] == "invalid_password"  # type: ignore[attr-defined]
    assert member.person.closed_at is None


@pytest.mark.parametrize(("status", "code"), [("verifier", "leads_a_group")])
def test_a_leader_steps_down_first(
    client: TestClient, world: World, status: str, code: str
) -> None:
    member = add_member(world, status)
    response = close(client, member)
    assert (response.status_code, response.json()["error"]["code"]) == (409, code)  # type: ignore[attr-defined]
    assert member.person.closed_at is None


def test_an_admin_and_the_owner_hand_over_first(client: TestClient, world: World) -> None:
    _church, _group, admin = world.add_church("Elsewhere")
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    world.session.flush()
    for person, pw in ((admin, password),):
        response = close(client, Member(person, pw))
        assert (response.status_code, response.json()["error"]["code"]) == (409, "leads_a_church")  # type: ignore[attr-defined]
    owner_password = secrets.token_urlsafe(16)
    world.owner.password_hash = hash_password(owner_password)
    world.session.flush()
    response = close(client, Member(world.owner, owner_password))
    assert (response.status_code, response.json()["error"]["code"]) == (409, "leads_a_church")  # type: ignore[attr-defined]


def test_a_revoked_person_cannot_close_their_account(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.request(
        "DELETE", f"{API}/me", headers=headers, json={"password": member.password}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")
    assert member.person.closed_at is None


def test_closing_needs_a_token_and_is_not_for_older_accounts(
    client: TestClient, session: Session
) -> None:
    assert client.request("DELETE", f"{API}/me", json={"password": "x" * 12}).status_code == 401
    older = signup(client, session, "workhost", "old-host4@example.com")
    response = client.request(
        "DELETE", f"{API}/me", headers=older.headers, json={"password": "x" * 12}
    )
    assert response.status_code == 403


def test_wrong_passwords_are_counted_and_then_throttled(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    codes = [
        client.request(
            "DELETE", f"{API}/me", headers=headers, json={"password": secrets.token_urlsafe(12)}
        ).status_code
        for _ in range(6)
    ]
    assert codes == [403, 403, 403, 403, 403, 429]
    blocked = client.request(
        "DELETE", f"{API}/me", headers=headers, json={"password": member.password}
    )
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert member.person.closed_at is None
    failures = world.session.scalars(
        select(LoginHistory).where(
            LoginHistory.user_id == member.person.id, LoginHistory.succeeded.is_(False)
        )
    ).all()
    assert len(failures) == 5


def test_an_older_account_with_the_same_address_keeps_its_login_trail(
    client: TestClient, session: Session, world: World
) -> None:
    older = signup(client, session, "workhost", "shared@example.com")
    assert older.headers
    member = add_member(world, "searcher", email="shared@example.com")
    client.post(f"{API}/auth/login", json={"email": "Shared@Example.com", "password": "x" * 12})
    assert close(client, member).status_code == 204  # type: ignore[attr-defined]
    kept = session.scalars(
        select(LoginHistory).where(
            LoginHistory.user_type == "workhost", LoginHistory.login_email == "shared@example.com"
        )
    ).all()
    assert kept, "the older account's login history was erased"
    cleared = session.scalars(select(LoginHistory).where(LoginHistory.user_type == "person")).all()
    assert cleared and all(r.login_email is None for r in cleared)
