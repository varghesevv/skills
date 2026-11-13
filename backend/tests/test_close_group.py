"""Closing a home group: the leader, being its last member, moves into another group."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import GroupInvitation, HomeGroup, MoveRequest, Notification, StatusChange
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def close(
    client: TestClient, who: Member, group: HomeGroup, into: HomeGroup, former: str = "provider"
) -> Any:
    return client.post(
        f"{API}/home-groups/{group.id}/close",
        headers=headers_of(client, who),
        json={"move_to_group_id": str(into.id), "former_leader_status": former},
    )


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


class Scene:
    """A VERIFIER alone in their group, and another group of the church to move into."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.lead, self.group = leader(world)
        self.other_lead, self.other = leader(world)


# --- closing ------------------------------------------------------------------------------------


def test_a_lone_verifier_closes_their_group_and_becomes_a_provider(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    client.post(f"{API}/verifier/group-invitations", headers=headers_of(client, scene.lead))
    response = close(client, scene.lead, scene.group, scene.other)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["closed_group"]["id"] == str(scene.group.id)
    assert body["joined_group"]["id"] == str(scene.other.id) and body["status"] == "provider"
    session.refresh(scene.group)
    session.refresh(scene.lead.person)
    person = scene.lead.person
    assert scene.group.closed_at is not None  # kept, with the date
    assert (person.status, person.home_group_id) == ("provider", scene.other.id)
    # Recorded as set by the church's ADMIN (here the OWNER), not by the person themselves.
    assert person.status_set_by_id == world.owner.id
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == person.id)).one()
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "step-down",
        "verifier",
        "provider",
        world.owner.id,
    )
    links = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == scene.group.id)
    ).all()
    assert links and all(link.revoked_at is not None for link in links)
    assert "member_moved_in" in kinds(session, scene.other_lead)
    assert "group_closed" in kinds(session, owner_member(world))
    check_rules(session)
    # Nobody can join it any more, and it is not offered.
    church = scene.group.church_id
    listed = client.get(f"{API}/churches/{church}/home-groups").json()["items"]
    assert str(scene.group.id) not in {g["id"] for g in listed}
    signup = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "New Applicant",
            "email": f"applicant-{secrets.token_hex(4)}@example.com",
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(scene.group.id),
        },
    )
    assert signup.status_code == 422 and signup.json()["error"]["code"] == "invalid_choice"
    # They no longer lead.
    assert (
        client.get(f"{API}/verifier/applicants", headers=headers_of(client, scene.lead)).status_code
        == 403
    )


def test_a_verifier_may_become_a_searcher_instead(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    assert close(client, scene.lead, scene.group, scene.other, "searcher").status_code == 200
    session.refresh(scene.lead.person)
    assert scene.lead.person.status == "searcher"


def test_the_owner_who_leads_a_lone_group_keeps_their_status(
    client: TestClient, session: Session, world: World
) -> None:
    other_lead, other = leader(world)
    owner = owner_member(world)
    response = close(client, owner, world.group, other, "keep")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "owner"
    session.refresh(world.owner)
    session.refresh(world.group)
    assert world.owner.status == "owner" and world.owner.home_group_id == other.id
    assert world.group.closed_at is not None
    assert (
        session.scalars(select(StatusChange).where(StatusChange.person_id == world.owner.id)).all()
        == []
    )
    assert "group_closed" not in kinds(session, owner)  # they are the church's ADMIN themselves
    check_rules(session)


def test_an_admin_who_leads_a_lone_group_keeps_their_status(
    client: TestClient, session: Session, world: World
) -> None:
    church, group, admin = world.add_church("Hope Church")
    lead = make_person(church, None, "verifier", home_group_id=None)
    other = HomeGroup(church_id=church.id, name="Harbour", leader_id=lead.id)
    session.add(other)
    session.flush()
    lead.home_group_id = other.id
    session.add(lead)
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    session.flush()
    response = close(client, Member(admin, password), group, other, "keep")
    assert response.status_code == 200, response.text
    session.refresh(admin)
    assert admin.status == "admin" and admin.home_group_id == other.id
    check_rules(session)


# --- who and what -------------------------------------------------------------------------------


def test_a_group_with_other_members_does_not_close(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    add_member(world, "pending", group=scene.group)  # even an applicant is a member
    refused = close(client, scene.lead, scene.group, scene.other)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "group_not_empty"
    assert session.scalar(select(HomeGroup.closed_at).where(HomeGroup.id == scene.group.id)) is None
    assert (
        session.scalar(select(HomeGroup.leader_id).where(HomeGroup.id == scene.group.id))
        == scene.lead.person.id
    )


def test_the_group_to_join_must_be_another_open_one_of_the_church(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    same = close(client, scene.lead, scene.group, scene.group)
    assert same.status_code == 422 and same.json()["error"]["code"] == "invalid_choice"
    _, elsewhere, _ = world.add_church("Hope Church")
    assert close(client, scene.lead, scene.group, elsewhere).status_code == 422
    scene.other.closed_at = datetime.now(UTC)
    session.flush()
    assert close(client, scene.lead, scene.group, scene.other).status_code == 422
    assert session.scalar(select(HomeGroup.closed_at).where(HomeGroup.id == scene.group.id)) is None


def test_the_status_must_fit_the_leader(client: TestClient, world: World) -> None:
    scene = Scene(world)
    assert close(client, scene.lead, scene.group, scene.other, "keep").status_code == 422
    assert (
        close(client, owner_member(world), world.group, scene.other, "provider").status_code == 422
    )


def test_only_the_leader_of_an_open_group_closes_it(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    for who in (scene.other_lead, owner_member(world), add_member(world, "provider")):
        assert close(client, who, scene.group, scene.other).status_code in (403, 404)
    assert close(client, owner_member(world), scene.group, scene.other).status_code == 404
    assert close(client, scene.other_lead, scene.group, scene.other).status_code == 404
    revoked = add_member(world, "revoked", last_home_group_id=scene.group.id)
    assert close(client, revoked, scene.group, scene.other).status_code == 403
    unknown = client.post(
        f"{API}/home-groups/00000000-0000-4000-8000-000000000000/close",
        headers=headers_of(client, scene.lead),
        json={"move_to_group_id": str(scene.other.id), "former_leader_status": "provider"},
    )
    assert unknown.status_code == 404
    assert (
        client.post(
            f"{API}/home-groups/{scene.group.id}/close",
            json={"move_to_group_id": str(scene.other.id), "former_leader_status": "provider"},
        ).status_code
        == 401
    )
    assert close(client, scene.lead, scene.group, scene.other).status_code == 200
    again = close(client, scene.lead, scene.group, scene.other)
    assert again.status_code in (403, 404)  # they no longer lead anything
    session.refresh(scene.group)
    assert scene.group.closed_at is not None


# --- what else changes --------------------------------------------------------------------------


def test_moves_into_the_closed_group_end_and_the_members_are_told(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    mover = add_member(world, "provider", group=scene.other)
    asked = client.post(
        f"{API}/move-requests",
        headers=headers_of(client, mover),
        json={"home_group_id": str(scene.group.id)},
    )
    assert asked.status_code == 201
    assert close(client, scene.lead, scene.group, scene.other).status_code == 200
    request = session.get(MoveRequest, asked.json()["id"])
    assert request is not None and request.cancelled_at is not None
    assert "move_cancelled" in kinds(session, mover)


def test_the_revoked_of_a_closed_group_stay_on_the_churchs_list(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    out = add_member(world, "revoked", last_home_group_id=scene.group.id)
    assert close(client, scene.lead, scene.group, scene.other).status_code == 200
    listed = client.get(
        f"{API}/verifier/revoked", headers=headers_of(client, owner_member(world))
    ).json()
    row = next(r for r in listed["items"] if r["id"] == str(out.person.id))
    assert row["removed_from"]["id"] == str(scene.group.id)
    check_rules(session)


def test_the_groups_are_locked_in_a_fixed_order(
    client: TestClient, session: Session, world: World
) -> None:
    """The closing group is taken for update and the joined one for sharing, in id order, so two
    leaders closing into each other's groups cannot wait for each other. Scenes are made until the
    closing group's id is both lower and higher than the joined group's."""
    seen: set[bool] = set()
    for _ in range(60):
        scene = Scene(world)
        statements: list[tuple[str, Any]] = []

        def record(
            conn: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            *rest: Any,
            sink: list[tuple[str, Any]] = statements,
        ) -> None:
            if "home_groups" in statement and (
                "FOR UPDATE" in statement or "FOR SHARE" in statement
            ):
                sink.append((statement, parameters))

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", record)
        try:
            assert close(client, scene.lead, scene.group, scene.other).status_code == 200
        finally:
            event.remove(bind, "before_cursor_execute", record)
        locks = [
            (str(next(iter(params.values())) if isinstance(params, dict) else params[0]), stmt)
            for stmt, params in statements
        ]
        wanted = {str(scene.group.id), str(scene.other.id)}
        ordered = [(i, stmt) for i, stmt in locks if i in wanted]
        assert [i for i, _ in ordered[:2]] == sorted(wanted, key=str)
        by_id = dict(ordered)
        assert "FOR UPDATE" in by_id[str(scene.group.id)]
        assert "FOR SHARE" in by_id[str(scene.other.id)]
        seen.add(str(scene.group.id) < str(scene.other.id))
        if len(seen) == 2:
            break
    assert seen == {True, False}


def test_the_new_kind_is_known() -> None:
    assert "group_closed" in notifications.KINDS
