"""Inviting an ADMIN, which creates a church: the invitation, its link, and acceptance."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.core.config import get_settings
from app.core.security import hash_token
from app.models import AdminInvitation, Church, HomeGroup, Notification, Person, StatusChange
from app.services import notifications, rate_limit
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import add_member
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db

INVITE = f"{API}/owner/churches"
LIST = f"{API}/owner/churches/invitations"
LOOKUP = f"{API}/admin-invitations/lookup"
ACCEPT = f"{API}/admin-invitations/accept"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    churches.limiter.reset()
    rate_limit.signup_limiter.reset()
    rate_limit.link_lookup_limiter.reset()


def invite(client: TestClient, world: World, name: str = "Hope Church", email: str = "") -> Any:
    email = email or f"minister-{secrets.token_hex(3)}@example.com"
    return client.post(
        INVITE,
        headers=headers_of(client, owner_member(world)),
        json={"church_name": name, "email": email},
    )


def accept_body(token: str, **extra: Any) -> dict[str, Any]:
    body = {
        "token": token,
        "full_name": "Mina Minister",
        "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
        "password": secrets.token_urlsafe(16),
        "home_group_name": "Lakeside",
    }
    body.update(extra)
    return body


# --- inviting -----------------------------------------------------------------------------------


def test_the_owner_invites_and_the_token_is_stored_hashed(
    client: TestClient, session: Session, world: World
) -> None:
    response = invite(client, world, email="Mina@Example.com")
    assert response.status_code == 201
    body = response.json()
    assert len(body["token"]) >= 43  # 256 bits
    row = session.get(AdminInvitation, body["id"])
    assert row is not None
    assert row.token_hash == hash_token(body["token"]) and body["token"] not in row.token_hash
    assert row.email == "mina@example.com" and row.church_name == "Hope Church"
    days = (row.expires_at - datetime.now(UTC)).total_seconds() / 86400
    assert 13.9 < days <= 14  # 14 days
    assert row.invited_by_id == world.owner.id
    listed = client.get(LIST, headers=headers_of(client, owner_member(world))).json()["items"]
    assert [(i["church_name"], i["email"], i["expired"]) for i in listed] == [
        ("Hope Church", "mina@example.com", False)
    ]
    assert body["token"] not in str(listed)


def test_only_the_owner_invites(client: TestClient, world: World) -> None:
    lead, _ = leader(world)
    for who in (lead, add_member(world, "provider"), add_member(world, "pending")):
        response = client.post(
            INVITE,
            headers=headers_of(client, who),
            json={"church_name": "Hope Church", "email": "m@example.com"},
        )
        assert response.status_code == 403
        assert client.get(LIST, headers=headers_of(client, who)).status_code == 403
    assert (
        client.post(INVITE, json={"church_name": "Hope", "email": "m@example.com"}).status_code
        == 401
    )


def test_the_name_and_the_address_must_be_free(client: TestClient, world: World) -> None:
    taken = invite(client, world, name=world.church.name.upper())
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "church_name_taken"
    assert invite(client, world, name="Hope Church", email="m@example.com").status_code == 201
    same_name = invite(client, world, name="hope church")
    assert same_name.status_code == 409 and same_name.json()["error"]["code"] == "church_name_taken"
    same_address = invite(client, world, name="Other Church", email="M@example.com")
    assert same_address.status_code == 409
    assert same_address.json()["error"]["code"] == "invitation_exists"
    member = add_member(world, "provider")
    existing = invite(client, world, name="Third Church", email=str(member.person.email))
    assert existing.status_code == 409 and existing.json()["error"]["code"] == "account_exists"
    assert invite(client, world, name="x", email="not-an-address").status_code == 422


# --- looking at the invitation ------------------------------------------------------------------


def test_the_invited_person_sees_the_church_and_only_the_domain(
    client: TestClient, world: World
) -> None:
    token = invite(client, world, email="mina@minister.example.org").json()["token"]
    response = client.post(LOOKUP, json={"token": token})
    assert response.status_code == 200
    assert response.json() == {"church_name": "Hope Church", "email_domain": "minister.example.org"}
    assert "mina" not in response.text


@pytest.mark.parametrize("how", ["unknown", "expired", "cancelled", "accepted"])
def test_every_bad_link_is_the_same_404(
    client: TestClient, session: Session, world: World, how: str
) -> None:
    created = invite(client, world).json()
    token = created["token"]
    row = session.get(AdminInvitation, created["id"])
    assert row is not None
    if how == "unknown":
        token = secrets.token_urlsafe(32)
    elif how == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif how == "cancelled":
        row.cancelled_at, row.email = datetime.now(UTC), None
    else:
        row.accepted_at, row.email = datetime.now(UTC), None
    session.flush()
    answers = {
        client.post(LOOKUP, json={"token": token}).text,
        client.post(ACCEPT, json=accept_body(token)).text,
    }
    assert len(answers) == 1
    assert client.post(LOOKUP, json={"token": token}).status_code == 404


def test_lookups_are_limited_per_address(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LINK_LOOKUP_MAX_PER_HOUR", "2")
    get_settings.cache_clear()
    try:
        token = invite(client, world).json()["token"]
        assert client.post(LOOKUP, json={"token": token}).status_code == 200
        assert client.post(LOOKUP, json={"token": token}).status_code == 200
        limited = client.post(LOOKUP, json={"token": token})
        assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
    finally:
        get_settings.cache_clear()


# --- accepting ----------------------------------------------------------------------------------


def test_accepting_creates_the_church_its_group_and_its_admin(
    client: TestClient, session: Session, world: World
) -> None:
    created = invite(client, world, email="mina@example.com").json()
    body = accept_body(created["token"])
    response = client.post(ACCEPT, json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "admin"
    church = session.get(Church, result["church_id"])
    admin = session.get(Person, result["id"])
    assert church is not None and admin is not None
    group = session.scalars(select(HomeGroup).where(HomeGroup.church_id == church.id)).one()
    assert (church.name, church.admin_id) == ("Hope Church", admin.id)
    assert (group.name, group.leader_id) == ("Lakeside", admin.id)
    assert (admin.status, admin.home_group_id, admin.church_id) == ("admin", group.id, church.id)
    assert admin.email == "mina@example.com"  # the invited address, nothing typed twice
    assert admin.status_set_by_id == world.owner.id
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == admin.id)).one()
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "appoint",
        None,
        "admin",
        world.owner.id,
    )
    invitation = session.get(AdminInvitation, created["id"])
    assert invitation is not None and invitation.accepted_at is not None
    assert invitation.email is None  # personal data goes once decided
    told = session.scalars(
        select(Notification).where(Notification.person_id == world.owner.id)
    ).all()
    assert [(n.kind, n.subject_id) for n in told] == [("church_created", admin.id)]
    assert "church_created" in notifications.KINDS
    check_rules(session)
    # The new ADMIN signs in with the invited address and leads their church at once.
    login = client.post(
        f"{API}/auth/login",
        json={"email": "mina@example.com", "password": body["password"]},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get(f"{API}/me", headers=headers).json()
    assert me["status"] == "admin" and me["church"]["name"] == "Hope Church"
    assert client.get(f"{API}/verifier/applicants", headers=headers).status_code == 200


def test_a_link_works_once(client: TestClient, world: World) -> None:
    token = invite(client, world).json()["token"]
    assert client.post(ACCEPT, json=accept_body(token)).status_code == 201
    assert client.post(ACCEPT, json=accept_body(token)).status_code == 404
    assert client.post(LOOKUP, json={"token": token}).status_code == 404


def test_a_name_taken_meanwhile_or_a_number_in_use_is_refused_and_nothing_is_made(
    client: TestClient, session: Session, world: World
) -> None:
    token = invite(client, world, name="Hope Church").json()["token"]
    world.add_church("hope church")  # an open church takes the name before it is accepted
    refused = client.post(ACCEPT, json=accept_body(token))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "church_name_taken"
    other = invite(client, world, name="Harbour Church").json()["token"]
    member = add_member(world, "provider")
    busy = client.post(
        ACCEPT, json=accept_body(other, mobile_number=str(member.person.mobile_number))
    )
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "account_exists"
    assert session.scalars(select(Church).where(Church.name == "Harbour Church")).first() is None
    # Both invitations stay open for another try.
    assert (
        len(client.get(LIST, headers=headers_of(client, owner_member(world))).json()["items"]) == 2
    )


def test_the_acceptance_is_checked_like_a_signup(client: TestClient, world: World) -> None:
    token = invite(client, world).json()["token"]
    for bad in (
        {"password": "short"},
        {"full_name": "x"},
        {"mobile_number": "not a number"},
        {"home_group_name": " "},
    ):
        assert client.post(ACCEPT, json=accept_body(token, **bad)).status_code == 422
    assert client.post(LOOKUP, json={"token": token}).status_code == 200  # still open


def test_acceptances_are_limited_per_address(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGNUP_MAX_PER_HOUR", "1")
    get_settings.cache_clear()
    try:
        token = invite(client, world).json()["token"]
        assert client.post(ACCEPT, json=accept_body(token)).status_code == 201
        second = client.post(ACCEPT, json=accept_body(token))
        assert second.status_code == 429
    finally:
        get_settings.cache_clear()


def test_the_current_owner_is_recorded_not_whoever_sent_the_invitation(
    client: TestClient, session: Session, world: World
) -> None:
    created = invite(client, world).json()
    row = session.get(AdminInvitation, created["id"])
    assert row is not None
    row.invited_by_id = add_member(world, "provider").person.id  # someone else sent it
    session.flush()
    result = client.post(ACCEPT, json=accept_body(created["token"])).json()
    admin = session.get(Person, result["id"])
    assert admin is not None and admin.status_set_by_id == world.owner.id
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == admin.id)).one()
    assert change.changed_by_id == world.owner.id


# --- cancelling ---------------------------------------------------------------------------------


def test_cancelling_clears_the_address_and_ends_the_link(
    client: TestClient, session: Session, world: World
) -> None:
    created = invite(client, world, email="mina@example.com").json()
    owner = owner_member(world)
    url = f"{LIST}/{created['id']}"
    assert client.delete(url, headers=headers_of(client, owner)).status_code == 204
    row = session.get(AdminInvitation, created["id"])
    assert row is not None and row.cancelled_at is not None and row.email is None
    assert client.post(LOOKUP, json={"token": created["token"]}).status_code == 404
    assert client.get(LIST, headers=headers_of(client, owner)).json()["items"] == []
    assert client.delete(url, headers=headers_of(client, owner)).status_code == 404
    # The address may be invited again.
    assert invite(client, world, email="mina@example.com").status_code == 201


def test_an_accepted_invitation_cannot_be_cancelled(client: TestClient, world: World) -> None:
    created = invite(client, world).json()
    client.post(ACCEPT, json=accept_body(created["token"]))
    owner = owner_member(world)
    assert (
        client.delete(f"{LIST}/{created['id']}", headers=headers_of(client, owner)).status_code
        == 404
    )


def test_an_expired_invitation_is_listed_as_such(
    client: TestClient, session: Session, world: World
) -> None:
    created = invite(client, world).json()
    row = session.get(AdminInvitation, created["id"])
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    session.flush()
    listed = client.get(LIST, headers=headers_of(client, owner_member(world))).json()["items"]
    assert [i["expired"] for i in listed] == [True]
    # An expired invitation does not block the name or the address.
    assert invite(client, world, name="Hope Church", email="again@example.com").status_code == 201
