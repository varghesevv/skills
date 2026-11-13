"""Starting a home group: the request, the approval, and a group started at once."""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password
from app.models import GroupRequest, HomeGroup, Notification, StatusChange
from app.services import group_requests, notifications
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


def test_an_owner_who_leads_a_lone_group_starts_another_and_the_old_one_closes(
    client: TestClient, session: Session, world: World
) -> None:
    old = world.group
    response = ask(client, owner_member(world), "Lakeside")
    assert response.status_code == 201 and response.json()["group"]["name"] == "Lakeside"
    session.refresh(old)
    assert old.closed_at is not None  # the OWNER was its only member
    session.refresh(world.owner)
    assert world.owner.home_group_id != old.id
    check_rules(session)


def test_an_owner_who_leads_a_group_with_members_names_a_successor(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")  # a member of the OWNER's group
    owner = owner_member(world)
    refused = ask(client, owner, "Lakeside")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    assert session.scalars(select(GroupRequest)).first() is None
    done = client.post(
        URL,
        headers=headers_of(client, owner),
        json={"group_name": "Lakeside", "successor_id": str(member.person.id)},
    )
    assert done.status_code == 201
    session.refresh(world.group)
    session.refresh(member.person)
    assert world.group.leader_id == member.person.id and member.person.status == "verifier"
    check_rules(session)


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


def test_a_leader_may_ask_and_the_request_says_they_lead(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    created = ask(client, lead, "Lakeside")
    assert created.status_code == 201
    assert created.json()["request"]["requester_leads_a_group"] is True
    assert session.scalars(select(GroupRequest)).one().state == "open"
    # Nothing moves until the ADMIN decides.
    session.refresh(lead.person)
    assert lead.person.home_group_id == group.id


def test_approving_a_leaders_request_hands_their_old_group_on(
    client: TestClient, session: Session, world: World
) -> None:
    lead, old = leader(world)
    heir = add_member(world, "searcher", group=old)
    request_id = ask(client, lead, "Lakeside").json()["request"]["id"]
    owner = owner_member(world)
    refused = decide(client, owner, request_id, "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(old)
    assert old.leader_id == lead.person.id  # nothing changed
    approved = client.post(
        f"{URL}/{request_id}/approve",
        headers=headers_of(client, owner),
        json={"successor_id": str(heir.person.id)},
    )
    assert approved.status_code == 200, approved.text
    session.refresh(old)
    session.refresh(heir.person)
    session.refresh(lead.person)
    new_group = session.scalars(select(HomeGroup).where(HomeGroup.name == "Lakeside")).one()
    assert (old.leader_id, heir.person.status) == (heir.person.id, "verifier")
    assert (new_group.leader_id, lead.person.home_group_id) == (lead.person.id, new_group.id)
    assert lead.person.status == "verifier"
    check_rules(session)


def test_a_lone_leaders_old_group_closes_when_the_request_is_approved(
    client: TestClient, session: Session, world: World
) -> None:
    lead, old = leader(world)
    request_id = ask(client, lead, "Lakeside").json()["request"]["id"]
    assert decide(client, owner_member(world), request_id, "approve").status_code == 200
    session.refresh(old)
    assert old.closed_at is not None
    check_rules(session)


def test_a_successor_must_belong_to_the_old_group(
    client: TestClient, session: Session, world: World
) -> None:
    lead, old = leader(world)
    add_member(world, "searcher", group=old)
    outsider = add_member(world, "provider")  # another group
    request_id = ask(client, lead, "Lakeside").json()["request"]["id"]
    refused = client.post(
        f"{URL}/{request_id}/approve",
        headers=headers_of(client, owner_member(world)),
        json={"successor_id": str(outsider.person.id)},
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
    # A successor named for someone who leads nothing is a mistake, not ignored.
    plain = add_member(world, "provider")
    other_id = ask(client, plain, "Harbour").json()["request"]["id"]
    wrong = client.post(
        f"{URL}/{other_id}/approve",
        headers=headers_of(client, owner_member(world)),
        json={"successor_id": str(outsider.person.id)},
    )
    assert wrong.status_code == 422


def test_a_requester_who_became_a_leader_meanwhile_needs_a_successor(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")
    created = ask(client, member, "Lakeside").json()["request"]
    assert created["requester_leads_a_group"] is False
    old_group = world.add_group(member.person, "Quicker")  # they lead another group now
    add_member(world, "searcher", group=old_group)  # which has another member
    listed = client.get(URL, headers=headers_of(client, owner_member(world))).json()["items"]
    assert listed[0]["requester_leads_a_group"] is True
    refused = decide(client, owner_member(world), created["id"], "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(member.person)
    assert member.person.home_group_id == old_group.id  # nothing moved


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


def test_the_list_is_paged(client: TestClient, world: World) -> None:
    for n in range(3):
        ask(client, add_member(world, "provider"), f"Group {n}")
    owner = owner_member(world)
    page = client.get(
        URL, headers=headers_of(client, owner), params={"limit": 2, "offset": 1}
    ).json()
    assert len(page["items"]) == 2 and page["total"] == 3
    assert (
        client.get(URL, headers=headers_of(client, owner), params={"limit": 101}).status_code == 422
    )
    assert (
        client.get(URL, headers=headers_of(client, owner), params={"offset": -1}).status_code == 422
    )


def test_a_name_taken_at_the_same_moment_is_refused_by_the_database(
    client: TestClient, session: Session, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = add_member(world, "provider")
    request_id = ask(client, member, "Hilltop").json()["request"]["id"]
    world.add_group(add_member(world, "provider").person, "hilltop")
    # The check says the name is free (as it would if the other group were made a moment later);
    # the unique index of open names still refuses it, and nothing is half done.
    monkeypatch.setattr("app.services.group_requests._name_taken", lambda *_: False)
    refused = decide(client, owner_member(world), request_id, "approve")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "group_name_taken"
    session.refresh(member.person)
    assert member.person.status == "provider"
    assert session.get(GroupRequest, request_id).state == "open"  # type: ignore[union-attr]


def test_an_admin_revoked_while_deciding_decides_nothing(session: Session, world: World) -> None:
    member = add_member(world, "provider")
    request = GroupRequest(
        requester_id=member.person.id, church_id=world.church.id, group_name="Hilltop"
    )
    session.add(request)
    stale = add_member(world, "provider").person  # in the database a PROVIDER, not an ADMIN
    session.flush()
    session.expunge(stale)
    stale.status = "owner"  # what the request thought it was when it was authorised
    with pytest.raises(ApiError) as caught:
        group_requests.approve(session, stale, request.id)
    assert caught.value.status_code == 403
