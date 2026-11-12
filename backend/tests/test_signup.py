"""Sign-up, change of choice while pending, and home group invitation links."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.models import GroupInvitation, Notification, Person, StatusChange, Vouch
from app.services import rate_limit
from tests.api_helpers import API
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    churches.limiter.reset()
    rate_limit.signup_limiter.reset()
    rate_limit.link_lookup_limiter.reset()


def details(**extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "full_name": "New Applicant",
        "email": f"applicant-{secrets.token_hex(4)}@example.com",
        "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
        "password": secrets.token_urlsafe(16),
        "requested_status": "searcher",
    }
    body.update(extra)
    return body


def sign_up(client: TestClient, world: World, **extra: Any) -> tuple[Any, dict[str, Any]]:
    body = details(**extra)
    if "invitation_token" not in body:
        body.setdefault("home_group_id", str(world.group.id))
    return client.post(f"{API}/auth/signup", json=body), body


def person_by_email(session: Session, email: str) -> Person:
    return session.scalars(select(Person).where(Person.email == email.lower())).one()


# ---- sign-up ---------------------------------------------------------------------------------


def test_sign_up_creates_a_pending_person_in_the_chosen_group(
    client: TestClient, session: Session, world: World
) -> None:
    response, body = sign_up(client, world, requested_status="provider")
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    person = person_by_email(session, body["email"])
    assert (person.status, person.requested_status) == ("pending", "provider")
    assert person.home_group_id == world.group.id and person.church_id == world.church.id
    assert person.status_set_by_id is None
    assert person.password_hash is not None and body["password"] not in person.password_hash
    assert body["password"] not in response.text


def test_sign_up_records_the_history_and_tells_the_leader(
    client: TestClient, session: Session, world: World
) -> None:
    _, body = sign_up(client, world)
    person = person_by_email(session, body["email"])
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == person.id)).one()
    assert (change.from_status, change.to_status, change.kind) == (None, "pending", "signup")
    note = session.scalars(select(Notification).where(Notification.subject_id == person.id)).one()
    assert note.person_id == world.owner.id and note.kind == "applicant_new"
    assert note.read_at is None


def test_a_new_applicant_can_log_in_and_sees_their_application(
    client: TestClient, world: World
) -> None:
    _, body = sign_up(client, world)
    member = Member.__new__(Member)
    member.email, member.password = body["email"], body["password"]
    headers = bearer(login(client, member))
    me = client.get(f"{API}/me", headers=headers).json()
    assert me["status"] == "pending" and me["home_group"]["id"] == str(world.group.id)
    assert me["leader"] == {"name": world.owner.full_name}


@pytest.mark.parametrize("status", ["pending", "provider ", "verifier", "owner", ""])
def test_only_searcher_or_provider_can_be_applied_for(
    client: TestClient, world: World, status: str
) -> None:
    response, _ = sign_up(client, world, requested_status=status)
    if status == "provider ":
        assert response.status_code == 422
    else:
        assert response.status_code == 422


def test_sign_up_needs_a_group_or_a_link_but_not_both(client: TestClient, world: World) -> None:
    none = client.post(f"{API}/auth/signup", json=details())
    both = client.post(
        f"{API}/auth/signup",
        json=details(home_group_id=str(world.group.id), invitation_token="x" * 20),
    )
    assert none.status_code == both.status_code == 422


def test_a_group_that_is_closed_or_unknown_is_refused_alike(
    client: TestClient, world: World
) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Soon closed")
    check_rules(world.session)
    group.closed_at = datetime.now(UTC)
    leader.status = "provider"
    leader.home_group_id = world.group.id
    check_rules(world.session)
    closed, _ = sign_up(client, world, home_group_id=str(group.id))
    unknown, _ = sign_up(client, world, home_group_id="00000000-0000-4000-8000-000000000000")
    assert closed.status_code == unknown.status_code == 422
    assert closed.json() == unknown.json()


def test_an_email_or_number_in_use_is_refused_with_one_answer(
    client: TestClient, world: World
) -> None:
    taken = world.add_person("searcher", email="taken@example.com", mobile_number="+971500000555")
    by_email, _ = sign_up(client, world, email="taken@example.com")
    by_number, _ = sign_up(client, world, mobile_number="+971500000555")
    assert by_email.status_code == by_number.status_code == 409
    assert by_email.json() == by_number.json()
    assert by_email.json()["error"]["code"] == "account_exists"
    assert taken.email not in by_email.text


def test_the_email_of_a_revoked_person_is_still_taken(client: TestClient, world: World) -> None:
    person = world.add_person("searcher", email="revoked-one@example.com")
    person.status = "revoked"
    person.home_group_id = None
    world.session.flush()
    response, _ = sign_up(client, world, email="revoked-one@example.com")
    assert response.status_code == 409


def test_the_email_of_someone_who_left_can_be_used_again(client: TestClient, world: World) -> None:
    person = world.add_person("searcher", email="left@example.com", mobile_number="+971500000556")
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    world.session.flush()
    response, _ = sign_up(client, world, email="left@example.com", mobile_number="+971500000556")
    assert response.status_code == 201


def test_email_is_matched_without_regard_to_case(client: TestClient, world: World) -> None:
    world.add_person("searcher", email="mixed@example.com")
    response, _ = sign_up(client, world, email="Mixed@Example.COM")
    assert response.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [{"password": "short"}, {"email": "no-at-sign"}, {"mobile_number": "12"}, {"full_name": "A"}],
)
def test_bad_details_are_refused_without_echoing_the_password(
    client: TestClient, world: World, bad: dict[str, str]
) -> None:
    response, body = sign_up(client, world, **bad)
    assert response.status_code == 422
    assert body["password"] not in response.text


def test_sign_up_is_limited_per_address(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGNUP_MAX_PER_HOUR", "2")
    get_settings.cache_clear()
    try:
        codes = [sign_up(client, world)[0].status_code for _ in range(3)]
        assert codes == [201, 201, 429]
    finally:
        get_settings.cache_clear()


# ---- change of choice ---------------------------------------------------------------------------


def applicant(world: World, **extra: Any) -> Member:
    return add_member(world, "pending", requested_status="searcher", **extra)


def test_a_pending_applicant_changes_group_and_what_they_apply_for(
    client: TestClient, session: Session, world: World
) -> None:
    other_leader = world.add_person("provider")
    other = world.add_group(other_leader, "Other group")
    member = applicant(world)
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me/application",
        headers=headers,
        json={"home_group_id": str(other.id), "requested_status": "provider"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["home_group"]["id"] == str(other.id)
    assert body["requested_status"] == "provider"
    note = session.scalars(
        select(Notification).where(
            Notification.subject_id == member.person.id, Notification.person_id == other_leader.id
        )
    ).one()
    assert note.kind == "applicant_new"


def test_choosing_a_group_in_another_church_moves_the_applicant_there(
    client: TestClient, world: World
) -> None:
    church, group, admin = world.add_church("Elsewhere")
    member = applicant(world)
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me/application", headers=headers, json={"home_group_id": str(group.id)}
    )
    assert response.status_code == 200
    assert response.json()["church"]["id"] == str(church.id)
    assert member.person.church_id == church.id and admin is not None


def test_vouches_already_received_still_count_after_a_change(
    client: TestClient, world: World
) -> None:
    voucher = world.add_person("searcher")
    member = applicant(world)
    world.session.add(Vouch(applicant_id=member.person.id, voucher_id=voucher.id))
    world.session.flush()
    other_leader = world.add_person("provider")
    other = world.add_group(other_leader, "Other group")
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me/application", headers=headers, json={"home_group_id": str(other.id)}
    )
    assert response.json()["vouch_count"] == 1


def test_changing_only_what_they_apply_for_does_not_notify_anyone(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world)
    headers = bearer(login(client, member))
    client.put(f"{API}/me/application", headers=headers, json={"requested_status": "provider"})
    assert (
        session.scalars(
            select(Notification).where(Notification.subject_id == member.person.id)
        ).all()
        == []
    )


def test_changing_to_the_same_group_does_not_notify_again(
    client: TestClient, session: Session, world: World
) -> None:
    member = applicant(world)
    headers = bearer(login(client, member))
    client.put(
        f"{API}/me/application", headers=headers, json={"home_group_id": str(world.group.id)}
    )
    assert (
        session.scalars(
            select(Notification).where(Notification.subject_id == member.person.id)
        ).all()
        == []
    )


@pytest.mark.parametrize("status", ["searcher", "provider", "verifier"])
def test_only_a_pending_application_can_be_changed(
    client: TestClient, world: World, status: str
) -> None:
    member = add_member(world, status)
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me/application", headers=headers, json={"requested_status": "provider"}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (409, "not_pending")


def test_a_revoked_person_cannot_change_an_application(client: TestClient, world: World) -> None:
    member = applicant(world)
    headers = bearer(login(client, member))
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.put(
        f"{API}/me/application", headers=headers, json={"requested_status": "provider"}
    )
    assert response.status_code == 403


def test_the_application_needs_a_token_and_a_real_choice(client: TestClient, world: World) -> None:
    assert (
        client.put(f"{API}/me/application", json={"requested_status": "provider"}).status_code
        == 401
    )
    member = applicant(world)
    headers = bearer(login(client, member))
    assert client.put(f"{API}/me/application", headers=headers, json={}).status_code == 422
    unknown = client.put(
        f"{API}/me/application",
        headers=headers,
        json={"home_group_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (422, "invalid_choice")


# ---- group invitation links -----------------------------------------------------------------


def leader_headers(client: TestClient, world: World) -> dict[str, str]:
    leader = add_member(world, "verifier")
    return bearer(login(client, leader))


def test_a_leader_creates_a_link_and_the_token_is_stored_only_as_a_hash(
    client: TestClient, session: Session, world: World
) -> None:
    headers = leader_headers(client, world)
    created = client.post(f"{API}/verifier/group-invitations", headers=headers)
    assert created.status_code == 201
    token = created.json()["token"]
    assert len(token) >= 43  # at least 256 bits, as url-safe text
    row = session.scalars(select(GroupInvitation)).one()
    assert row.token_hash == hash_token(token) and token not in row.token_hash
    assert row.expires_at > datetime.now(UTC) + timedelta(days=29)
    listing = client.get(f"{API}/verifier/group-invitations", headers=headers).json()["items"]
    assert [i["id"] for i in listing] == [created.json()["id"]]
    assert "token" not in listing[0]


def test_a_link_leads_to_its_group_and_signing_up_through_it_chooses_the_group(
    client: TestClient, session: Session, world: World
) -> None:
    leader = add_member(world, "provider")
    group = world.add_group(leader.person, "Linked group")
    leader.person.status = "verifier"
    headers = bearer(login(client, leader))
    token = client.post(f"{API}/verifier/group-invitations", headers=headers).json()["token"]
    info = client.post(f"{API}/group-invitations/lookup", json={"token": token})  # no login needed
    assert info.status_code == 200
    assert info.json() == {
        "church_name": "First church",
        "home_group_name": "Linked group",
        "leader_name": leader.person.full_name,
    }
    response = client.post(
        f"{API}/auth/signup", json=details(invitation_token=token, requested_status="provider")
    )
    assert response.status_code == 201
    joined = session.get(Person, response.json()["id"])
    assert joined is not None and joined.home_group_id == group.id and joined.status == "pending"


@pytest.mark.parametrize("how", ["unknown", "expired", "revoked", "group closed"])
def test_every_failure_of_a_link_looks_the_same(
    client: TestClient, session: Session, world: World, how: str
) -> None:
    leader = add_member(world, "provider")
    group = world.add_group(leader.person, "Linked")
    leader.person.status = "verifier"
    headers = bearer(login(client, leader))
    created = client.post(f"{API}/verifier/group-invitations", headers=headers).json()
    token = created["token"]
    row = session.get(GroupInvitation, created["id"])
    assert row is not None
    if how == "unknown":
        token = secrets.token_urlsafe(32)
    elif how == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.flush()
    elif how == "revoked":
        client.delete(f"{API}/verifier/group-invitations/{created['id']}", headers=headers)
    else:
        check_rules(session)
        group.closed_at = datetime.now(UTC)
        leader.person.status = "provider"
        leader.person.home_group_id = world.group.id
        check_rules(session)
    lookup = client.post(f"{API}/group-invitations/lookup", json={"token": token})
    signup_attempt = client.post(f"{API}/auth/signup", json=details(invitation_token=token))
    assert lookup.status_code == 404
    assert lookup.json()["error"]["code"] == "not_found"
    assert signup_attempt.status_code == 422
    assert signup_attempt.json()["error"]["code"] == "invalid_choice"


def test_a_revoked_link_stops_working_and_leaves_the_list(client: TestClient, world: World) -> None:
    headers = leader_headers(client, world)
    created = client.post(f"{API}/verifier/group-invitations", headers=headers).json()
    assert (
        client.delete(
            f"{API}/verifier/group-invitations/{created['id']}", headers=headers
        ).status_code
        == 204
    )
    assert client.get(f"{API}/verifier/group-invitations", headers=headers).json()["items"] == []
    assert (
        client.post(f"{API}/group-invitations/lookup", json={"token": created["token"]}).status_code
        == 404
    )


def test_a_leader_cannot_revoke_a_link_of_another_group(client: TestClient, world: World) -> None:
    headers = leader_headers(client, world)
    created = client.post(f"{API}/verifier/group-invitations", headers=headers).json()
    other_church, other_group, other_admin = world.add_church("Elsewhere")
    del other_church, other_group
    other = Member(other_admin, secrets.token_urlsafe(16))
    other_admin.password_hash = __import__("app.core.security", fromlist=["x"]).hash_password(
        other.password
    )
    world.session.flush()
    other_headers = bearer(login(client, other))
    response = client.delete(
        f"{API}/verifier/group-invitations/{created['id']}", headers=other_headers
    )
    assert response.status_code == 404
    assert (
        client.post(f"{API}/group-invitations/lookup", json={"token": created["token"]}).status_code
        == 200
    )


@pytest.mark.parametrize("status", ["pending", "searcher", "provider"])
def test_only_leaders_manage_links(client: TestClient, world: World, status: str) -> None:
    member = add_member(world, status)
    headers = bearer(login(client, member))
    for call in (
        lambda: client.post(f"{API}/verifier/group-invitations", headers=headers),
        lambda: client.get(f"{API}/verifier/group-invitations", headers=headers),
    ):
        response = call()
        assert response.status_code == 403
    assert client.post(f"{API}/verifier/group-invitations").status_code == 401


def test_link_lookups_are_limited_per_address(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LINK_LOOKUP_MAX_PER_HOUR", "2")
    get_settings.cache_clear()
    try:
        codes = [
            client.post(
                f"{API}/group-invitations/lookup", json={"token": secrets.token_urlsafe(32)}
            ).status_code
            for _ in range(3)
        ]
        assert codes == [404, 404, 429]
    finally:
        get_settings.cache_clear()


def test_a_group_invitation_lookup_keeps_the_token_out_of_the_address(
    client: TestClient, world: World
) -> None:
    headers = leader_headers(client, world)
    token = client.post(f"{API}/verifier/group-invitations", headers=headers).json()["token"]
    assert client.get(f"{API}/group-invitations/{token}").status_code in (404, 405)
    assert client.post(f"{API}/group-invitations/lookup", json={"token": token}).status_code == 200


def test_each_address_has_its_own_sign_up_and_link_limit(
    client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    monkeypatch.setenv("SIGNUP_MAX_PER_HOUR", "1")
    monkeypatch.setenv("LINK_LOOKUP_MAX_PER_HOUR", "1")
    get_settings.cache_clear()
    try:
        lookup = {"token": secrets.token_urlsafe(32)}
        with (
            TestClient(app, client=("198.51.100.1", 1)) as first,
            TestClient(app, client=("198.51.100.2", 1)) as second,
        ):
            for tc, expected in ((first, [201, 429]), (second, [201, 429])):
                body = {**details(), "home_group_id": str(world.group.id)}
                again = {**details(), "home_group_id": str(world.group.id)}
                codes = [tc.post(f"{API}/auth/signup", json=b).status_code for b in (body, again)]
                assert codes == expected
            assert first.post(f"{API}/group-invitations/lookup", json=lookup).status_code == 404
            assert first.post(f"{API}/group-invitations/lookup", json=lookup).status_code == 429
            assert second.post(f"{API}/group-invitations/lookup", json=lookup).status_code == 404
    finally:
        get_settings.cache_clear()


def test_a_leader_who_handed_their_group_on_has_no_links_to_give(
    client: TestClient, world: World
) -> None:
    """An ADMIN can be a member of a group without leading it: links come from the leader."""
    church, group, admin = world.add_church("Elsewhere")
    successor = make_person(church, group, "verifier")
    world.session.add(successor)
    world.session.flush()
    group.leader_id = successor.id  # the ADMIN hands the group on and keeps their status
    check_rules(world.session)
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    world.session.flush()
    headers = bearer(login(client, Member(admin, password)))
    for call in (
        lambda: client.post(f"{API}/verifier/group-invitations", headers=headers),
        lambda: client.get(f"{API}/verifier/group-invitations", headers=headers),
    ):
        response = call()
        assert (response.status_code, response.json()["error"]["code"]) == (409, "no_home_group")


def test_an_admin_who_leads_their_group_can_give_links(client: TestClient, world: World) -> None:
    _church, _group, admin = world.add_church("Elsewhere")
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    world.session.flush()
    headers = bearer(login(client, Member(admin, password)))
    assert client.post(f"{API}/verifier/group-invitations", headers=headers).status_code == 201


def test_an_application_admitted_in_the_meantime_is_not_changed(
    client: TestClient, session: Session, world: World
) -> None:
    """The person was loaded as pending, then admitted by a leader before the change ran."""
    member = applicant(world)
    headers = bearer(login(client, member))
    other_leader = world.add_person("provider")
    other = world.add_group(other_leader, "Other group")
    # A change made behind the loaded copy, as another request would make it.
    session.execute(
        update(Person)
        .where(Person.id == member.person.id)
        .values(status="searcher")
        .execution_options(synchronize_session=False)  # the loaded copy stays "pending"
    )
    response = client.put(
        f"{API}/me/application", headers=headers, json={"home_group_id": str(other.id)}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (409, "not_pending")
    session.expire_all()
    assert member.person.home_group_id == world.group.id


def test_a_refused_choice_leaves_nothing_half_changed(client: TestClient, world: World) -> None:
    member = applicant(world)
    headers = bearer(login(client, member))
    response = client.put(
        f"{API}/me/application",
        headers=headers,
        json={
            "home_group_id": "00000000-0000-4000-8000-000000000000",
            "requested_status": "provider",
        },
    )
    assert response.status_code == 422
    world.session.expire_all()
    assert member.person.requested_status == "searcher"
