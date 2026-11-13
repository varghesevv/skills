"""Starting a home group: the request, the approval, and a group started at once."""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import GroupRequest, HomeGroup, Notification, StatusChange
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db

URL = f"{API}/group-requests"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def ask(client: TestClient, who: Member, name: str = "Hilltop") -> Any:
    return client.post(URL, headers=headers_of(client, who), json={"group_name": name})


def decide(client: TestClient, who: Member, request_id: str, action: str) -> Any:
    return client.post(f"{URL}/{request_id}/{action}", headers=headers_of(client, who))


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


def church_admin(world: World) -> Member:
    """The ADMIN of a second church (the first church's ADMIN is the OWNER)."""
    church, _, admin = world.add_church("Hope Church")
    member = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(member.password)
    world.session.flush()
    return member


# --- asking -------------------------------------------------------------------------------------


def test_a_member_asks_and_the_admin_is_told(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    response = ask(client, member)
    assert response.status_code == 201
    body = response.json()
    assert body["group"] is None
    assert body["request"]["state"] == "open"
    assert body["request"]["group_name"] == "Hilltop"
    assert body["request"]["requester"]["id"] == str(member.person.id)
    assert body["request"]["requester_leads_a_group"] is False
    admin_notes = session.scalars(
        select(Notification).where(Notification.person_id == world.owner.id)
    ).all()
    assert [(n.kind, n.subject_id) for n in admin_notes] == [
        ("group_request_new", member.person.id)
    ]
    assert session.scalars(select(HomeGroup).where(HomeGroup.name == "Hilltop")).first() is None


def test_the_requester_sees_their_own_requests_and_no_one_elses(
    client: TestClient, world: World
) -> None:
    mine, other = add_member(world, "searcher"), add_member(world, "provider")
    ask(client, mine, "Hilltop")
    ask(client, other, "Harbour")
    own = client.get(URL, headers=headers_of(client, mine)).json()["items"]
    assert [r["group_name"] for r in own] == ["Hilltop"]


@pytest.mark.parametrize("status", ["pending", "revoked"])
def test_only_admitted_people_ask(client: TestClient, world: World, status: str) -> None:
    extra = {"last_home_group_id": world.group.id} if status == "revoked" else {}
    response = ask(client, add_member(world, status, **extra))
    assert response.status_code == 403
    assert response.json()["error"]["code"] in ("not_admitted", "account_revoked")
    assert client.post(URL, json={"group_name": "Hilltop"}).status_code == 401


def test_one_open_request_at_a_time_and_a_name_that_is_free(
    client: TestClient, world: World
) -> None:
    member = add_member(world, "provider")
    assert ask(client, member).status_code == 201
    again = ask(client, member, "Harbour")
    assert again.status_code == 409 and again.json()["error"]["code"] == "request_open"
    taken = ask(client, add_member(world, "searcher"), world.group.name.upper())
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "group_name_taken"
    assert ask(client, add_member(world, "searcher"), " ").status_code == 422


# --- the ADMIN or the OWNER starts a group at once -----------------------------------------------


def test_an_admin_without_a_group_of_their_own_starts_one_at_once(
    client: TestClient, session: Session, world: World
) -> None:
    # The ADMIN of a second church led its first group, then handed it on: they stay a member.
    church, group, admin = world.add_church("Hope Church")
    successor = make_person(church, group, "verifier")
    session.add(successor)
    session.flush()
    group.leader_id = successor.id
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    session.flush()
    check_rules(session)
    response = ask(client, Member(admin, password), "Lakeside")
    assert response.status_code == 201
    body = response.json()
    assert body["group"]["name"] == "Lakeside"
    assert body["request"]["state"] == "approved"
    session.refresh(admin)
    assert admin.status == "admin"  # their status does not change
    created = session.scalars(select(HomeGroup).where(HomeGroup.name == "Lakeside")).one()
    assert created.leader_id == admin.id and admin.home_group_id == created.id
    check_rules(session)


def test_a_leader_needs_a_successor_first(
    client: TestClient, session: Session, world: World
) -> None:
    refused = ask(client, owner_member(world))  # the OWNER leads their group
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    assert session.scalars(select(GroupRequest)).first() is None


# --- deciding -----------------------------------------------------------------------------------


def test_the_admin_approves_and_the_member_leads_a_new_group(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    owner = owner_member(world)
    request_id = ask(client, member).json()["request"]["id"]
    response = decide(client, owner, request_id, "approve")
    assert response.status_code == 200
    group = session.scalars(select(HomeGroup).where(HomeGroup.name == "Hilltop")).one()
    assert response.json()["group"] == {"id": str(group.id), "name": "Hilltop"}
    session.refresh(member.person)
    person = member.person
    assert (person.status, person.home_group_id) == ("verifier", group.id)
    assert group.leader_id == person.id and person.status_set_by_id == owner.person.id
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == person.id)).one()
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "appoint",
        "provider",
        "verifier",
        owner.person.id,
    )
    assert "group_request_approved" in kinds(session, member)
    assert session.get(GroupRequest, request_id).state == "approved"  # type: ignore[union-attr]
    # They lead now: the leader's screens work.
    assert (
        client.get(f"{API}/verifier/applicants", headers=headers_of(client, member)).status_code
        == 200
    )
    check_rules(session)


def test_a_searcher_becomes_a_verifier_too(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "searcher")
    request_id = ask(client, member).json()["request"]["id"]
    decide(client, owner_member(world), request_id, "approve")
    session.refresh(member.person)
    assert member.person.status == "verifier"


def test_the_admin_declines_and_the_member_may_ask_again(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    request_id = ask(client, member).json()["request"]["id"]
    assert decide(client, owner_member(world), request_id, "decline").status_code == 204
    session.refresh(member.person)
    assert member.person.status == "provider"
    assert "group_request_declined" in kinds(session, member)
    assert ask(client, member, "Harbour").status_code == 201
    states = [
        r["state"] for r in client.get(URL, headers=headers_of(client, member)).json()["items"]
    ]
    assert sorted(states) == ["declined", "open"]


def test_a_request_is_decided_once(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    owner = owner_member(world)
    request_id = ask(client, member).json()["request"]["id"]
    assert decide(client, owner, request_id, "approve").status_code == 200
    for action in ("approve", "decline"):
        again = decide(client, owner, request_id, action)
        assert again.status_code == 409 and again.json()["error"]["code"] == "not_open"


def test_who_may_decide_and_see_the_open_requests(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    request_id = ask(client, member).json()["request"]["id"]
    # Not leaders of the church: a VERIFIER, a provider.
    lead, _ = leader(world)
    for who in (lead, add_member(world, "provider")):
        assert decide(client, who, request_id, "approve").status_code == 403
    # An ADMIN of another church does not see it or decide it.
    other = church_admin(world)
    assert client.get(URL, headers=headers_of(client, other)).json()["items"] == []
    assert decide(client, other, request_id, "approve").status_code == 404
    unknown = "00000000-0000-4000-8000-000000000000"
    assert decide(client, owner_member(world), unknown, "approve").status_code == 404
    # The church's ADMIN (here the OWNER) sees it, the OWNER sees every church's.
    seen = client.get(URL, headers=headers_of(client, owner_member(world))).json()["items"]
    assert [r["id"] for r in seen] == [request_id]


def test_a_requester_who_leads_needs_a_successor_before_approval(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    created = ask(client, lead, "Lakeside").json()["request"]
    assert created["requester_leads_a_group"] is True
    refused = decide(client, owner_member(world), created["id"], "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(lead.person)
    assert lead.person.home_group_id == group.id  # nothing moved
    assert session.scalars(select(HomeGroup).where(HomeGroup.name == "Lakeside")).first() is None


def test_a_requester_who_left_or_was_revoked_cannot_be_made_leader(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    request_id = ask(client, member).json()["request"]["id"]
    member.person.status = "revoked"
    member.person.last_home_group_id = member.person.home_group_id
    member.person.home_group_id = None
    session.flush()
    refused = decide(client, owner_member(world), request_id, "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "requester_unavailable"


def test_a_name_taken_meanwhile_is_refused_at_approval(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    request_id = ask(client, member, "Hilltop").json()["request"]["id"]
    world.add_group(add_member(world, "provider").person, "hilltop")  # taken in the meantime
    refused = decide(client, owner_member(world), request_id, "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "group_name_taken"


def test_the_new_kinds_are_known(session: Session) -> None:
    assert {"group_request_new", "group_request_approved", "group_request_declined"} <= set(
        notifications.KINDS
    )
