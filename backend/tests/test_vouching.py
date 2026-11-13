"""Vouch links and vouches: who may make a link, who may vouch, limits, and the failures that all
look alike."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.models import Notification, Person, Vouch, VouchLink
from app.services import rate_limit
from tests.api_helpers import API
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    rate_limit.link_lookup_limiter.reset()
    rate_limit.vouch_attempt_limiter.reset()


def headers_of(client: TestClient, member: Member) -> dict[str, str]:
    return bearer(login(client, member))


def applicant(world: World, requested: str = "searcher") -> Member:
    return add_member(world, "pending", requested_status=requested)


def make_link(client: TestClient, member: Member) -> str:
    response = client.post(f"{API}/me/vouch-link", headers=headers_of(client, member))
    assert response.status_code == 201, response.text
    token: str = response.json()["token"]
    return token


def lookup(client: TestClient, member: Member, token: str) -> Any:
    return client.post(
        f"{API}/vouch-links/lookup", headers=headers_of(client, member), json={"token": token}
    )


def vouch(client: TestClient, member: Member, token: str) -> Any:
    return client.post(
        f"{API}/vouch-links/vouch", headers=headers_of(client, member), json={"token": token}
    )


def test_a_pending_applicant_makes_a_link_that_is_stored_hashed(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world)
    headers = headers_of(client, member)
    assert client.get(f"{API}/me/vouch-link", headers=headers).json() == {
        "active": False,
        "expires_at": None,
    }
    response = client.post(f"{API}/me/vouch-link", headers=headers)
    assert response.status_code == 201
    token = response.json()["token"]
    assert len(token) >= 43  # 256 bits
    link = session.scalars(select(VouchLink).where(VouchLink.person_id == member.person.id)).one()
    assert link.token_hash == hash_token(token) and token not in link.token_hash
    state = client.get(f"{API}/me/vouch-link", headers=headers).json()
    assert state["active"] is True and "token" not in state


def test_a_new_link_ends_the_old_one(client: TestClient, world: World) -> None:
    member = applicant(world)
    voucher = add_member(world, "searcher")
    old = make_link(client, member)
    new = make_link(client, member)
    assert lookup(client, voucher, old).status_code == 404
    assert lookup(client, voucher, new).status_code == 200


def test_a_searcher_who_applies_to_provide_may_make_a_link(
    client: TestClient, world: World
) -> None:
    member = add_member(world, "searcher", requested_status="provider")
    token = make_link(client, member)
    voucher = add_member(world, "provider")
    info = lookup(client, voucher, token).json()
    assert info["requested_status"] == "provider"


@pytest.mark.parametrize("status", ["searcher", "provider", "verifier", "admin", "owner"])
def test_admitted_people_who_do_not_apply_have_no_link(
    client: TestClient, world: World, status: str
) -> None:
    member = add_member(world, status)
    response = client.post(f"{API}/me/vouch-link", headers=headers_of(client, member))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_applying"
    assert client.get(f"{API}/me/vouch-link", headers=headers_of(client, member)).status_code == 409


def test_a_revoked_person_has_no_link(client: TestClient, world: World) -> None:
    member = add_member(world, "revoked", last_home_group_id=world.group.id)
    response = client.post(f"{API}/me/vouch-link", headers=headers_of(client, member))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_revoked"


def test_the_link_shows_who_asks_and_what_for_but_no_number(
    client: TestClient, world: World
) -> None:
    member = applicant(world, "provider")
    voucher = add_member(world, "searcher")
    response = lookup(client, voucher, make_link(client, member))
    assert response.status_code == 200
    assert response.json() == {
        "applicant_name": member.person.full_name,
        "church_name": world.church.name,
        "home_group_name": world.group.name,
        "requested_status": "provider",
        "already_vouched": False,
    }
    assert member.person.mobile_number not in response.text


def test_a_pending_person_cannot_open_a_link(client: TestClient, world: World) -> None:
    token = make_link(client, applicant(world))
    other = applicant(world)
    for call in (lookup, vouch):
        response = call(client, other, token)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_admitted"


def test_a_link_needs_a_login(client: TestClient, world: World) -> None:
    token = make_link(client, applicant(world))
    assert client.post(f"{API}/vouch-links/lookup", json={"token": token}).status_code == 401
    assert client.post(f"{API}/vouch-links/vouch", json={"token": token}).status_code == 401


@pytest.mark.parametrize("status", ["searcher", "provider", "verifier"])
def test_any_admitted_person_may_vouch_and_the_applicant_is_notified(
    client: TestClient, session: Session, world: World, status: str
) -> None:
    member = applicant(world)
    voucher = add_member(world, status)
    token = make_link(client, member)
    response = vouch(client, voucher, token)
    assert response.status_code == 201
    row = session.get(Vouch, response.json()["id"])
    assert row is not None
    assert (row.applicant_id, row.voucher_id) == (member.person.id, voucher.person.id)
    note = session.scalars(
        select(Notification).where(
            Notification.person_id == member.person.id, Notification.kind == "vouch_received"
        )
    ).one()
    assert note.subject_id == voucher.person.id
    check_rules(session)


def test_a_leader_of_another_church_may_vouch(client: TestClient, world: World) -> None:
    _, _, admin = world.add_church()
    voucher = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(voucher.password)
    world.session.flush()
    assert vouch(client, voucher, make_link(client, applicant(world))).status_code == 201


def test_the_owner_may_vouch(client: TestClient, world: World) -> None:
    voucher = Member(world.owner, secrets.token_urlsafe(16))
    world.owner.password_hash = hash_password(voucher.password)
    world.session.flush()
    assert vouch(client, voucher, make_link(client, applicant(world))).status_code == 201


def test_nobody_vouches_for_themselves(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher", requested_status="provider")
    token = make_link(client, member)
    for call in (lookup, vouch):
        response = call(client, member, token)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "cannot_vouch_self"


def test_one_vouch_each(client: TestClient, session: Session, world: World) -> None:
    token = make_link(client, applicant(world))
    voucher = add_member(world, "searcher")
    assert vouch(client, voucher, token).status_code == 201
    again = vouch(client, voucher, token)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_vouched"
    assert lookup(client, voucher, token).json()["already_vouched"] is True
    assert len(session.scalars(select(Vouch)).all()) == 1


def test_a_vouch_can_be_withdrawn_and_given_again(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world, "provider")
    token = make_link(client, member)
    voucher = add_member(world, "searcher")
    vouch_id = vouch(client, voucher, token).json()["id"]
    headers = headers_of(client, voucher)
    assert client.delete(f"{API}/vouches/{vouch_id}", headers=headers).status_code == 204
    assert client.delete(f"{API}/vouches/{vouch_id}", headers=headers).status_code == 204
    mine = client.get(f"{API}/me/vouches", headers=headers_of(client, member)).json()["items"]
    assert [v["live"] for v in mine] == [False]
    assert client.get(f"{API}/me", headers=headers_of(client, member)).json()["vouch_count"] == 0
    again = vouch(client, voucher, token)
    assert again.status_code == 201 and again.json()["id"] == vouch_id
    assert client.get(f"{API}/me", headers=headers_of(client, member)).json()["vouch_count"] == 1
    assert len(session.scalars(select(Vouch)).all()) == 1


def test_only_the_voucher_can_withdraw(client: TestClient, world: World) -> None:
    token = make_link(client, applicant(world))
    voucher = add_member(world, "searcher")
    vouch_id = vouch(client, voucher, token).json()["id"]
    other = add_member(world, "provider")
    response = client.delete(f"{API}/vouches/{vouch_id}", headers=headers_of(client, other))
    assert response.status_code == 404


def test_no_withdrawal_after_admission(client: TestClient, session: Session, world: World) -> None:
    member = applicant(world)
    voucher = add_member(world, "searcher")
    vouch_id = vouch(client, voucher, make_link(client, member)).json()["id"]
    member.person.status = "searcher"
    member.person.requested_status = None
    session.flush()
    response = client.delete(f"{API}/vouches/{vouch_id}", headers=headers_of(client, voucher))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_pending"
    assert session.get(Vouch, vouch_id).withdrawn_at is None  # type: ignore[union-attr]


def test_a_link_stops_working_once_the_person_is_admitted_or_gone(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world)
    voucher = add_member(world, "searcher")
    token = make_link(client, member)
    member.person.status = "searcher"
    member.person.requested_status = None
    session.flush()
    for call in (lookup, vouch):
        assert call(client, voucher, token).status_code == 404


@pytest.mark.parametrize("how", ["unknown", "expired", "revoked", "closed"])
def test_every_failure_is_the_same_404(
    client: TestClient, session: Session, world: World, how: str
) -> None:
    member = applicant(world)
    voucher = add_member(world, "searcher")
    token = make_link(client, member)
    link = session.scalars(select(VouchLink)).one()
    if how == "unknown":
        token = secrets.token_urlsafe(32)  # a well-formed token nobody made
    elif how == "expired":
        link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif how == "revoked":
        link.revoked_at = datetime.now(UTC)
    else:
        member.person.closed_at = datetime.now(UTC)
        member.person.home_group_id = None
        member.person.full_name = member.person.email = member.person.mobile_number = None
        member.person.password_hash = None
        session.execute(update(VouchLink).values(revoked_at=None))
    session.flush()
    bodies = set()
    for call in (lookup, vouch):
        response = call(client, voucher, token)
        assert response.status_code == 404
        bodies.add(response.text)
    assert len(bodies) == 1


def test_a_revoked_voucher_does_not_count_and_cannot_vouch(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world)
    voucher = add_member(world, "searcher")
    vouch(client, voucher, make_link(client, member))
    session.execute(
        update(Person)
        .where(Person.id == voucher.person.id)
        .values(status="revoked", home_group_id=None, last_home_group_id=world.group.id)
        .execution_options(synchronize_session=False)
    )
    session.flush()
    assert client.get(f"{API}/me", headers=headers_of(client, member)).json()["vouch_count"] == 0
    items = client.get(f"{API}/me/vouches", headers=headers_of(client, member)).json()["items"]
    assert [v["live"] for v in items] == [False]


def test_the_lists_of_vouches(client: TestClient, world: World) -> None:
    member = applicant(world)
    voucher = add_member(world, "provider")
    vouch(client, voucher, make_link(client, member))
    received = client.get(f"{API}/me/vouches", headers=headers_of(client, member)).json()["items"]
    assert len(received) == 1
    assert received[0]["voucher_name"] == voucher.person.full_name
    assert received[0]["church_name"] == world.church.name and received[0]["live"] is True
    assert "mobile" not in str(received) and "email" not in str(received)
    given = client.get(f"{API}/me/vouches-given", headers=headers_of(client, voucher)).json()
    assert given["items"][0]["applicant_name"] == member.person.full_name
    assert given["items"][0]["can_withdraw"] is True
    # A pending person has not vouched for anyone and may not look.
    assert (
        client.get(f"{API}/me/vouches-given", headers=headers_of(client, member)).status_code == 403
    )


def test_vouches_per_day_are_limited(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    monkeypatch.setenv("VOUCH_MAX_PER_DAY", "2")
    get_settings.cache_clear()
    try:
        voucher = add_member(world, "searcher")
        tokens = [make_link(client, applicant(world)) for _ in range(3)]
        assert vouch(client, voucher, tokens[0]).status_code == 201
        assert vouch(client, voucher, tokens[1]).status_code == 201
        blocked = vouch(client, voucher, tokens[2])
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
    finally:
        get_settings.cache_clear()


def test_lookups_are_limited_per_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    monkeypatch.setenv("LINK_LOOKUP_MAX_PER_HOUR", "2")
    get_settings.cache_clear()
    try:
        voucher = add_member(world, "searcher")
        token = make_link(client, applicant(world))
        assert lookup(client, voucher, token).status_code == 200
        assert lookup(client, voucher, token).status_code == 200
        assert lookup(client, voucher, token).status_code == 429
        # Vouching has its own count.
        assert vouch(client, voucher, token).status_code == 201
    finally:
        get_settings.cache_clear()


def test_the_lists_are_bounded_and_empty_when_there_is_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    member = applicant(world)
    assert client.get(f"{API}/me/vouches", headers=headers_of(client, member)).json() == {
        "items": []
    }
    monkeypatch.setattr("app.services.vouching.MAX_LISTED", 1)
    token = make_link(client, member)
    for _ in range(2):
        assert vouch(client, add_member(world, "searcher"), token).status_code == 201
    items = client.get(f"{API}/me/vouches", headers=headers_of(client, member)).json()["items"]
    assert len(items) == 1
