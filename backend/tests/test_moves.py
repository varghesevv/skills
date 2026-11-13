"""Moving between home groups: by agreement of three, and directly by an ADMIN or the OWNER."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import HomeGroup, MoveRequest, Notification, Person, StatusChange
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db

URL = f"{API}/move-requests"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def ask(client: TestClient, who: Member, group: HomeGroup) -> Any:
    return client.post(URL, headers=headers_of(client, who), json={"home_group_id": str(group.id)})


def act(client: TestClient, who: Member, request_id: str, what: str) -> Any:
    return client.post(f"{URL}/{request_id}/{what}", headers=headers_of(client, who))


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


class Scene:
    """Two groups of the first church, each with a leader, and a member of the first."""

    def __init__(self, world: World, status: str = "provider") -> None:
        self.world = world
        self.from_leader, self.from_group = leader(world)
        self.to_leader, self.to_group = leader(world)
        self.member = add_member(world, status, group=self.from_group)


# --- asking and agreeing ------------------------------------------------------------------------


def test_a_member_asks_and_both_leaders_are_told(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    response = ask(client, scene.member, scene.to_group)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["state"] == "open"
    assert body["agreed"] == {"person": True, "from_leader": False, "to_leader": False}
    assert body["from_group"]["id"] == str(scene.from_group.id)
    assert body["to_group"]["id"] == str(scene.to_group.id)
    for lead in (scene.from_leader, scene.to_leader):
        told = session.scalars(
            select(Notification).where(Notification.person_id == lead.person.id)
        ).all()
        assert [(n.kind, n.subject_id) for n in told] == [
            ("move_requested", scene.member.person.id)
        ]
    # Nothing moved yet.
    session.refresh(scene.member.person)
    assert scene.member.person.home_group_id == scene.from_group.id


def test_the_move_happens_with_the_last_agreement_in_any_order(
    client: TestClient, session: Session, world: World
) -> None:
    for first_is_from in (True, False):
        scene = Scene(world)
        request_id = ask(client, scene.member, scene.to_group).json()["id"]
        first, second = (
            (scene.from_leader, scene.to_leader)
            if first_is_from
            else (scene.to_leader, scene.from_leader)
        )
        halfway = act(client, first, request_id, "agree")
        assert halfway.status_code == 200 and halfway.json()["state"] == "open"
        session.refresh(scene.member.person)
        assert scene.member.person.home_group_id == scene.from_group.id  # two of three: not yet
        done = act(client, second, request_id, "agree")
        assert done.status_code == 200 and done.json()["state"] == "completed"
        session.refresh(scene.member.person)
        assert scene.member.person.home_group_id == scene.to_group.id
        assert scene.member.person.status == "provider"  # a move is not a change of status
        assert (
            session.scalars(
                select(StatusChange).where(StatusChange.person_id == scene.member.person.id)
            ).all()
            == []
        )
        assert "move_completed" in kinds(session, scene.member)
        check_rules(session)


def test_the_leaders_not_acting_are_told_when_it_completes(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    act(client, scene.from_leader, request_id, "agree")
    act(client, scene.to_leader, request_id, "agree")
    assert "member_moved_in" not in kinds(session, scene.to_leader)  # they made the last agreement
    assert "member_moved_out" in kinds(session, scene.from_leader)


def test_each_side_agrees_once_and_only_those_it_concerns_may(
    client: TestClient, world: World
) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    again = act(client, scene.member, request_id, "agree")  # asking was their agreement
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_agreed"
    assert act(client, scene.from_leader, request_id, "agree").status_code == 200
    twice = act(client, scene.from_leader, request_id, "agree")
    assert twice.status_code == 409 and twice.json()["error"]["code"] == "already_agreed"
    stranger = add_member(world, "provider")
    for call in ("agree", "cancel"):
        assert act(client, stranger, request_id, call).status_code == 404
    assert (
        act(client, scene.to_leader, "00000000-0000-4000-8000-000000000000", "agree").status_code
        == 404
    )


def test_the_lists_show_a_move_to_those_it_concerns(client: TestClient, world: World) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    for who in (scene.member, scene.from_leader, scene.to_leader):
        listed = client.get(URL, headers=headers_of(client, who)).json()
        assert [i["id"] for i in listed["items"]] == [request_id] and listed["total"] == 1
    other = add_member(world, "provider")
    assert client.get(URL, headers=headers_of(client, other)).json()["items"] == []
    page = client.get(URL, headers=headers_of(client, scene.member), params={"limit": 101})
    assert page.status_code == 422


# --- cancelling ---------------------------------------------------------------------------------


def test_the_member_or_a_leader_cancels_and_the_other_side_is_told(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    first = ask(client, scene.member, scene.to_group).json()["id"]
    assert act(client, scene.member, first, "cancel").json()["state"] == "cancelled"
    assert "move_cancelled" in kinds(session, scene.from_leader)
    assert "move_cancelled" in kinds(session, scene.to_leader)
    second = ask(client, scene.member, scene.to_group).json()["id"]  # a new one may be made
    assert act(client, scene.to_leader, second, "cancel").json()["state"] == "cancelled"
    assert "move_cancelled" in kinds(session, scene.member)
    again = act(client, scene.from_leader, second, "agree")
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_open"


def test_a_decided_move_cannot_be_cancelled(client: TestClient, world: World) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    act(client, scene.from_leader, request_id, "agree")
    act(client, scene.to_leader, request_id, "agree")
    refused = act(client, scene.member, request_id, "cancel")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_open"


# --- who may ask, and where ----------------------------------------------------------------------


def test_only_admitted_members_ask(client: TestClient, world: World) -> None:
    scene = Scene(world)
    pending = add_member(world, "pending", group=scene.from_group)
    refused = ask(client, pending, scene.to_group)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "not_admitted"
    revoked = add_member(world, "revoked", last_home_group_id=scene.from_group.id)
    assert ask(client, revoked, scene.to_group).status_code == 403
    assert client.post(URL, json={"home_group_id": str(scene.to_group.id)}).status_code == 401


def test_a_leader_steps_down_before_moving(client: TestClient, world: World) -> None:
    scene = Scene(world)
    refused = ask(client, scene.from_leader, scene.to_group)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "leads_a_group"
    owner = owner_member(world)  # the OWNER leads the first group
    assert ask(client, owner, scene.to_group).status_code == 409


def test_the_group_must_be_another_open_one_of_the_same_church(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    same = ask(client, scene.member, scene.from_group)
    assert same.status_code == 422 and same.json()["error"]["code"] == "invalid_choice"
    _, elsewhere, _ = world.add_church("Hope Church")
    assert ask(client, scene.member, elsewhere).status_code == 422
    scene.to_group.closed_at = datetime.now(UTC)
    session.flush()
    assert ask(client, scene.member, scene.to_group).status_code == 422
    unknown = client.post(
        URL,
        headers=headers_of(client, scene.member),
        json={"home_group_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert unknown.status_code == 422


def test_one_open_move_at_a_time_and_the_database_agrees(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    assert ask(client, scene.member, scene.to_group).status_code == 201
    again = ask(client, scene.member, scene.to_group)
    assert again.status_code == 409 and again.json()["error"]["code"] == "request_open"
    # The unique index backs the check: two open rows for one person are refused.
    session.add(
        MoveRequest(
            person_id=scene.member.person.id,
            from_group_id=scene.from_group.id,
            to_group_id=scene.to_group.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_asking_takes_a_shared_lock_on_the_groups(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        statements.append(statement)

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        assert ask(client, scene.member, scene.to_group).status_code == 201
    finally:
        event.remove(bind, "before_cursor_execute", record)
    locked = [s for s in statements if "home_groups" in s and "FOR SHARE" in s]
    assert len(locked) >= 2  # the group they leave and the group they join


# --- what changes before the last agreement ------------------------------------------------------


def test_a_member_who_became_a_leader_before_the_last_agreement_does_not_move(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    act(client, scene.from_leader, request_id, "agree")
    session.refresh(scene.from_group)
    # They are made the leader of their own group (the old leader steps down).
    scene.from_group.leader_id = scene.member.person.id
    scene.member.person.status = "verifier"
    scene.from_leader.person.status = "provider"
    session.flush()
    refused = act(client, scene.to_leader, request_id, "agree")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "leads_a_group"
    session.refresh(scene.member.person)
    assert scene.member.person.home_group_id == scene.from_group.id


def test_a_member_who_is_no_longer_in_the_group_does_not_move(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    act(client, scene.from_leader, request_id, "agree")
    scene.member.person.status = "revoked"
    scene.member.person.last_home_group_id = scene.member.person.home_group_id
    scene.member.person.home_group_id = None
    session.flush()
    refused = act(client, scene.to_leader, request_id, "agree")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "request_stale"


def test_a_new_leader_takes_over_the_agreement(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = ask(client, scene.member, scene.to_group).json()["id"]
    heir = add_member(world, "provider", group=scene.to_group)
    owner = owner_member(world)
    changed = client.put(
        f"{API}/home-groups/{scene.to_group.id}/leader",
        headers=headers_of(client, owner),
        json={"successor_id": str(heir.person.id), "former_leader_status": "provider"},
    )
    assert changed.status_code == 200
    assert act(client, scene.to_leader, request_id, "agree").status_code == 404  # no longer theirs
    assert act(client, heir, request_id, "agree").status_code == 200
    assert act(client, scene.from_leader, request_id, "agree").json()["state"] == "completed"


# --- directly by an ADMIN or the OWNER ----------------------------------------------------------


def direct(client: TestClient, who: Member, target: Member, group: HomeGroup) -> Any:
    return client.post(
        f"{API}/verifier/people/{target.person.id}/move",
        headers=headers_of(client, who),
        json={"home_group_id": str(group.id)},
    )


def test_the_owner_moves_a_member_without_the_agreements(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    pending_request = ask(client, scene.member, scene.to_group).json()["id"]
    response = direct(client, owner_member(world), scene.member, scene.to_group)
    assert response.status_code == 200, response.text
    assert response.json()["home_group"]["id"] == str(scene.to_group.id)
    session.refresh(scene.member.person)
    assert scene.member.person.home_group_id == scene.to_group.id
    assert "move_completed" in kinds(session, scene.member)
    assert "member_moved_out" in kinds(session, scene.from_leader)
    assert "member_moved_in" in kinds(session, scene.to_leader)
    assert session.get(MoveRequest, pending_request).cancelled_at is not None  # type: ignore[union-attr]
    check_rules(session)


def test_an_admin_moves_within_their_church_only(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    church, group, admin = world.add_church("Hope Church")
    admin.password_hash = hash_password("x" + secrets.token_hex(8))
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    session.flush()
    other_admin = Member(admin, password)
    assert direct(client, other_admin, scene.member, scene.to_group).status_code == 404


def test_the_direct_move_has_the_same_limits(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    owner = owner_member(world)
    leads = direct(client, owner, scene.from_leader, scene.to_group)
    assert leads.status_code == 409 and leads.json()["error"]["code"] == "leads_a_group"
    pending = add_member(world, "pending", group=scene.from_group)
    assert direct(client, owner, pending, scene.to_group).status_code == 403
    same = direct(client, owner, scene.member, scene.from_group)
    assert same.status_code == 422
    _, elsewhere, _ = world.add_church("Hope Church")
    assert direct(client, owner, scene.member, elsewhere).status_code == 422
    for who in (scene.from_leader, add_member(world, "provider"), scene.member):
        assert direct(client, who, scene.member, scene.to_group).status_code == 403
    assert (
        direct(client, owner, Member(world.owner, ""), scene.to_group).status_code == 404
    )  # oneself
    assert (
        client.post(f"{API}/verifier/people/{scene.member.person.id}/move", json={}).status_code
        == 401
    )


def test_the_new_kinds_are_known() -> None:
    assert {
        "move_requested",
        "move_completed",
        "move_cancelled",
        "member_moved_in",
        "member_moved_out",
    } <= set(notifications.KINDS)
    assert Person is not None
