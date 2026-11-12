"""GET and PUT /me for people, and the public list of churches and home groups."""

import secrets
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.core.config import get_settings
from app.models import HomeGroup, Person, Vouch
from tests.api_helpers import API, signup
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture(autouse=True)
def _fresh_limiter() -> None:
    churches.limiter.reset()


def me(client: TestClient, member: Member) -> dict[str, object]:
    response = client.get(f"{API}/me", headers=bearer(login(client, member)))
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


# ---- GET /me ---------------------------------------------------------------------------------


def test_me_shows_the_person_their_church_group_and_leader(
    client: TestClient, world: World
) -> None:
    leader = add_member(world, "provider")
    group = world.add_group(leader.person, "Riverside")
    applicant = add_member(world, "pending", requested_status="provider")
    applicant.person.home_group_id = group.id
    world.session.flush()
    body = me(client, applicant)
    assert body["status"] == "pending"
    assert body["requested_status"] == "provider"
    assert body["church"] == {"id": str(world.church.id), "name": "First church"}
    assert body["home_group"] == {"id": str(group.id), "name": "Riverside"}
    assert body["leader"] == {"name": leader.person.full_name}
    assert body["status_set_by"] is None
    assert body["email"] == applicant.email
    assert body["flagged_for_recheck"] is False
    assert body["vouch_count"] == 0
    assert "password_hash" not in body


def test_me_counts_only_live_vouches(client: TestClient, world: World) -> None:
    applicant = add_member(world, "pending")
    good = world.add_person("searcher")
    withdrawn = world.add_person("provider")
    revoked = world.add_person("searcher")
    for voucher in (good, withdrawn, revoked):
        world.session.add(Vouch(applicant_id=applicant.person.id, voucher_id=voucher.id))
    world.session.flush()
    withdrawn_vouch = world.session.query(Vouch).filter_by(voucher_id=withdrawn.id).one()
    withdrawn_vouch.withdrawn_at = datetime.now(UTC)
    revoked.status = "revoked"
    revoked.home_group_id = None
    world.session.flush()
    assert me(client, applicant)["vouch_count"] == 1


def test_me_names_who_set_the_status(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher", status_set_by_id=world.owner.id)
    assert me(client, member)["status_set_by"] == {"name": world.owner.full_name}


def test_a_revoked_person_can_still_read_me(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    member.person.status = "revoked"
    member.person.home_group_id = None
    member.person.last_home_group_id = world.group.id
    world.session.flush()
    response = client.get(f"{API}/me", headers=bearer(tokens))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "revoked"
    assert body["home_group"] is None and body["leader"] is None


def test_a_closed_account_cannot_read_me(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    tokens = login(client, member)
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    world.session.flush()
    assert client.get(f"{API}/me", headers=bearer(tokens)).status_code == 401


def test_me_still_answers_the_older_accounts_in_their_older_shape(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "old-host3@example.com", full_name="Old Host")
    body = client.get(f"{API}/me", headers=host.headers).json()
    assert body["user_type"] == "workhost" and body["full_name"] == "Old Host"
    assert "church" not in body


def test_me_needs_a_token(client: TestClient) -> None:
    assert client.get(f"{API}/me").status_code == 401


# ---- PUT /me ---------------------------------------------------------------------------------


def test_a_person_changes_their_name_and_mobile_number(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me",
        headers=headers,
        json={"full_name": "  New Name ", "mobile_number": "+971 55 111 2222"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "New Name"
    assert response.json()["mobile_number"] == "+971551112222"
    assert member.person.full_name == "New Name"


def test_a_field_left_out_keeps_its_value(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    before = member.person.mobile_number
    headers = bearer(login(client, member))
    assert (
        client.put(f"{API}/me", headers=headers, json={"full_name": "Only Name"}).status_code == 200
    )
    assert member.person.mobile_number == before


@pytest.mark.parametrize(
    "body",
    [{"full_name": None}, {"mobile_number": None}, {"full_name": "A"}, {"mobile_number": "12"}],
)
def test_bad_changes_are_refused(client: TestClient, world: World, body: dict[str, object]) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    assert client.put(f"{API}/me", headers=headers, json=body).status_code == 422


def test_a_mobile_number_in_use_is_refused_without_saying_whose(
    client: TestClient, world: World
) -> None:
    other = world.add_person("searcher", mobile_number="+971500000777")
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    response = client.put(f"{API}/me", headers=headers, json={"mobile_number": "+971500000777"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_exists"
    assert other.mobile_number not in response.text


def test_a_revoked_person_cannot_change_their_details(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = bearer(login(client, member))
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.put(f"{API}/me", headers=headers, json={"full_name": "New Name"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_revoked"


def test_put_me_needs_a_token(client: TestClient) -> None:
    assert client.put(f"{API}/me", json={"full_name": "Someone"}).status_code == 401


@pytest.mark.parametrize("user_type", ["workhost", "freelancer", "organisation", "admin"])
def test_put_me_refuses_the_older_accounts(
    client: TestClient, session: Session, user_type: str
) -> None:
    older = signup(client, session, user_type, f"old-{user_type}@example.com")
    response = client.put(f"{API}/me", headers=older.headers, json={"full_name": "Changed Name"})
    assert response.status_code == 403
    after = client.get(f"{API}/me", headers=older.headers).json()
    assert after.get("full_name") != "Changed Name"


def test_the_two_answers_of_me_can_be_told_apart(client: TestClient, world: World) -> None:
    assert me(client, add_member(world, "searcher"))["user_type"] == "person"


# ---- the public lists ---------------------------------------------------------------------------


def test_the_church_list_is_public_and_sorted_by_name(client: TestClient, world: World) -> None:
    world.add_church("Alpha")
    response = client.get(f"{API}/churches")  # no token
    assert response.status_code == 200
    items = response.json()["items"]
    assert [c["name"] for c in items] == ["Alpha", "First church"]
    assert set(items[0]) == {"id", "name"}


def test_closed_churches_are_not_listed(client: TestClient, world: World) -> None:
    church, _group, admin = world.add_church("Closing")
    church.closed_at = datetime.now(UTC)
    for person in world.session.query(Person).filter_by(church_id=church.id):
        person.closed_at = datetime.now(UTC)
        person.home_group_id = None
        person.full_name = person.email = person.mobile_number = person.password_hash = None
    for group in world.session.query(HomeGroup).filter_by(church_id=church.id):
        group.closed_at = datetime.now(UTC)
    check_rules(world.session)
    names = [c["name"] for c in client.get(f"{API}/churches").json()["items"]]
    assert "Closing" not in names and admin is not None


def test_home_groups_show_their_names_and_leaders_and_nothing_else(
    client: TestClient, world: World
) -> None:
    leader = world.add_person("provider")
    world.add_group(leader, "Beta group")
    response = client.get(f"{API}/churches/{world.church.id}/home-groups")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [g["name"] for g in items] == ["Beta group", "First group"]
    assert items[0]["leader_name"] == leader.full_name
    for item in items:
        assert set(item) == {"id", "name", "leader_name"}
    assert leader.email not in response.text and leader.mobile_number not in response.text


def test_closed_groups_are_not_listed(client: TestClient, world: World) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Short lived")
    check_rules(world.session)
    group.closed_at = datetime.now(UTC)
    leader.status = "provider"
    leader.home_group_id = world.group.id
    check_rules(world.session)
    names = [
        g["name"]
        for g in client.get(f"{API}/churches/{world.church.id}/home-groups").json()["items"]
    ]
    assert names == ["First group"]


def test_an_unknown_or_closed_church_is_not_found(client: TestClient, world: World) -> None:
    unknown = client.get(
        f"{API}/churches/{secrets.token_hex(16)[:8]}-0000-4000-8000-000000000000/home-groups"
    )
    assert unknown.status_code == 404
    church, _group, _admin = world.add_church("Soon closed")
    church.closed_at = datetime.now(UTC)
    for person in world.session.query(Person).filter_by(church_id=church.id):
        person.closed_at = datetime.now(UTC)
        person.home_group_id = None
        person.full_name = person.email = person.mobile_number = person.password_hash = None
    for group in world.session.query(HomeGroup).filter_by(church_id=church.id):
        group.closed_at = datetime.now(UTC)
    check_rules(world.session)
    closed = client.get(f"{API}/churches/{church.id}/home-groups")
    assert closed.status_code == 404
    assert closed.json() == unknown.json()  # the same answer: nothing shows which it was


def test_the_public_lists_are_limited_per_ip(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PUBLIC_LIST_MAX_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        for _ in range(3):
            assert client.get(f"{API}/churches").status_code == 200
        blocked = client.get(f"{API}/churches/{world.church.id}/home-groups")
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        assert blocked.json()["error"]["code"] == "rate_limited"
    finally:
        get_settings.cache_clear()


def test_each_ip_address_has_its_own_limit(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    monkeypatch.setenv("PUBLIC_LIST_MAX_PER_MINUTE", "2")
    get_settings.cache_clear()
    try:
        with (
            TestClient(app, client=("198.51.100.1", 1)) as first,
            TestClient(app, client=("198.51.100.2", 1)) as second,
        ):
            assert [first.get(f"{API}/churches").status_code for _ in range(3)] == [200, 200, 429]
            assert second.get(f"{API}/churches").status_code == 200  # another address, own bucket
    finally:
        get_settings.cache_clear()


def test_the_public_lists_never_grow_without_bound(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import directory

    monkeypatch.setattr(directory, "MAX_LISTED", 1)
    world.add_church("Zed")
    assert len(client.get(f"{API}/churches").json()["items"]) == 1
