"""A planned handover of the OWNER role: proposing, accepting, cancelling, and what moves."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Church,
    GroupInvitation,
    HandoverRequest,
    HomeGroup,
    Notification,
    Person,
    StatusChange,
)
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db

URL = f"{API}/owner/handover"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


class Scene:
    """The OWNER's church (with a member in their group and one in another group), and a second
    church whose ADMIN will be chosen."""

    def __init__(self, world: World) -> None:
        self.world = world
        session = world.session
        self.owner = owner_member(world)
        self.in_group = add_member(world, "provider")  # a member of the OWNER's group
        lead = make_person(world.church, None, "verifier", home_group_id=None)
        self.other_group = HomeGroup(church_id=world.church.id, name="Harbour", leader_id=lead.id)
        session.add(self.other_group)
        session.flush()
        lead.home_group_id = self.other_group.id
        session.add(lead)
        self.elsewhere = add_member(world, "searcher", group=self.other_group)
        self.church, self.group, admin = world.add_church("Hope Church")
        password = secrets.token_urlsafe(16)
        admin.password_hash = hash_password(password)
        self.admin = Member(admin, password)
        session.flush()
        check_rules(session)


def propose(client: TestClient, who: Member, body: dict[str, Any]) -> Any:
    return client.post(URL, headers=headers_of(client, who), json=body)


def full_body(scene: Scene, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "new_owner_id": str(scene.admin.person.id),
        "successor_admin_id": str(scene.elsewhere.person.id),
        "successor_leader_id": str(scene.in_group.person.id),
    }
    body.update(extra)
    return body


def owners(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Person)
            .where(Person.status == "owner", Person.closed_at.is_(None))
        )
        or 0
    )


def history(session: Session, who: Person) -> list[tuple[str, str | None, str, Any]]:
    rows = session.scalars(select(StatusChange).where(StatusChange.person_id == who.id))
    return sorted((c.kind, c.from_status, c.to_status, c.changed_by_id) for c in rows)


# --- the whole handover -------------------------------------------------------------------------


def test_the_chosen_admin_accepts_and_every_role_moves_in_one_step(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    session.add(
        GroupInvitation(
            home_group_id=world.group.id,
            created_by_id=world.owner.id,
            token_hash=secrets.token_hex(16),
            expires_at=datetime(2100, 1, 1, tzinfo=UTC),
        )
    )
    session.flush()
    created = propose(client, scene.owner, full_body(scene, former_owner_status="searcher"))
    assert created.status_code == 201, created.text
    assert owners(session) == 1  # nothing moves until the ADMIN accepts
    session.refresh(world.owner)
    assert world.owner.status == "owner"
    # Tokens carry only the person, so the sessions of before keep working as the statuses change.
    old_headers = headers_of(client, scene.owner)
    response = client.post(
        f"{URL}/{created.json()['id']}/accept", headers=headers_of(client, scene.admin)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["owner"]["id"] == str(scene.admin.person.id)
    assert (body["former_owner"]["id"], body["former_owner_status"]) == (
        str(world.owner.id),
        "searcher",
    )
    for person in (world.owner, scene.admin.person, scene.elsewhere.person, scene.in_group.person):
        session.refresh(person)
    session.refresh(world.church)
    session.refresh(world.group)
    session.refresh(scene.church)
    # The new OWNER, who stays the ADMIN of their own church.
    assert scene.admin.person.status == "owner" and scene.church.admin_id == scene.admin.person.id
    assert scene.admin.person.status_set_by_id is None
    # The outgoing OWNER: a searcher in their own group, set by the new OWNER.
    assert (world.owner.status, world.owner.home_group_id) == ("searcher", world.group.id)
    assert world.owner.status_set_by_id == scene.admin.person.id
    # The new ADMIN of their church and the new leader of their group.
    assert world.church.admin_id == scene.elsewhere.person.id
    assert scene.elsewhere.person.status == "admin"
    assert world.group.leader_id == scene.in_group.person.id
    assert scene.in_group.person.status == "verifier"
    assert owners(session) == 1
    assert history(session, scene.admin.person) == [("handover", "admin", "owner", world.owner.id)]
    assert history(session, world.owner) == [
        ("handover", "owner", "searcher", scene.admin.person.id)
    ]
    assert ("appoint", "searcher", "admin", scene.admin.person.id) in history(
        session, scene.elsewhere.person
    )
    assert ("appoint", "provider", "verifier", scene.admin.person.id) in history(
        session, scene.in_group.person
    )
    links = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == world.group.id)
    ).all()
    assert links and all(link.revoked_at is not None for link in links)
    check_rules(session)
    # The old sessions show the new statuses, and the new OWNER can do what only the OWNER does.
    assert client.get(f"{API}/me", headers=old_headers).json()["status"] == "searcher"
    invited = client.post(
        f"{API}/owner/churches",
        headers=headers_of(client, scene.admin),
        json={"church_name": "Third Church", "email": "third@example.com"},
    )
    assert invited.status_code == 201
    assert (
        client.post(
            f"{API}/owner/churches",
            headers=old_headers,
            json={"church_name": "Fourth Church", "email": "fourth@example.com"},
        ).status_code
        == 403
    )
    told = {
        n.kind
        for n in session.scalars(
            select(Notification).where(Notification.person_id == world.owner.id)
        )
    }
    assert "owner_handed_over" in told
    assert "owner_appointed" in {
        n.kind
        for n in session.scalars(
            select(Notification).where(Notification.person_id == scene.admin.person.id)
        )
    }


def test_one_person_may_take_both_the_church_and_the_group(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    body = full_body(scene, successor_admin_id=str(scene.in_group.person.id))
    created = propose(client, scene.owner, body)
    assert created.status_code == 201, created.text
    assert (
        client.post(
            f"{URL}/{created.json()['id']}/accept", headers=headers_of(client, scene.admin)
        ).status_code
        == 200
    )
    session.refresh(scene.in_group.person)
    session.refresh(world.group)
    assert (
        scene.in_group.person.status == "admin"
        and world.group.leader_id == scene.in_group.person.id
    )
    assert [h for h in history(session, scene.in_group.person) if h[0] == "appoint"] == [
        ("appoint", "provider", "admin", scene.admin.person.id)
    ]
    check_rules(session)


def test_with_nobody_to_take_over_the_outgoing_owner_keeps_the_roles(
    client: TestClient, session: Session, world: World
) -> None:
    # An OWNER alone in their church: no one to name, so they stay the ADMIN and the leader.
    admin_church, admin_group, admin = world.add_church("Hope Church")
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    session.flush()
    chosen = Member(admin, password)
    owner = owner_member(world)
    created = propose(client, owner, {"new_owner_id": str(admin.id)})
    assert created.status_code == 201, created.text
    assert (
        client.post(
            f"{URL}/{created.json()['id']}/accept", headers=headers_of(client, chosen)
        ).status_code
        == 200
    )
    session.refresh(world.owner)
    session.refresh(world.church)
    session.refresh(world.group)
    assert world.owner.status == "admin" and world.church.admin_id == world.owner.id
    assert world.group.leader_id == world.owner.id
    assert owners(session) == 1
    check_rules(session)


def test_a_church_with_members_in_other_groups_leaves_the_group_to_the_old_owner(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    # The OWNER is alone in their group but the church has others elsewhere: name only an ADMIN.
    session.execute(
        update(Person)
        .where(Person.id == scene.in_group.person.id)
        .values(home_group_id=scene.other_group.id)
    )
    session.expire_all()
    created = propose(
        client,
        scene.owner,
        {
            "new_owner_id": str(scene.admin.person.id),
            "successor_admin_id": str(scene.elsewhere.person.id),
        },
    )
    assert created.status_code == 201, created.text
    assert (
        client.post(
            f"{URL}/{created.json()['id']}/accept", headers=headers_of(client, scene.admin)
        ).status_code
        == 200
    )
    session.refresh(world.owner)
    session.refresh(world.group)
    assert (
        world.owner.status == "verifier" and world.group.leader_id == world.owner.id
    )  # keeps leading
    check_rules(session)


# --- proposing ----------------------------------------------------------------------------------


def test_the_chosen_must_be_the_admin_of_another_church(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    for bad in (
        scene.in_group.person.id,
        scene.elsewhere.person.id,
        world.owner.id,
        "00000000-0000-4000-8000-000000000000",
    ):
        refused = propose(client, scene.owner, full_body(scene, new_owner_id=str(bad)))
        assert refused.status_code == 422, (bad, refused.text)
        assert refused.json()["error"]["code"] == "invalid_choice"
    assert session.scalars(select(HandoverRequest)).first() is None


def test_successors_are_needed_when_there_are_other_members_and_must_belong(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    no_admin = propose(client, scene.owner, full_body(scene, successor_admin_id=None))
    assert no_admin.status_code == 409 and no_admin.json()["error"]["code"] == "successor_required"
    no_leader = propose(client, scene.owner, full_body(scene, successor_leader_id=None))
    assert (
        no_leader.status_code == 409 and no_leader.json()["error"]["code"] == "successor_required"
    )
    # A member of another church, and a member of another group, are not members where it counts.
    other_church = Member(make_person(scene.church, scene.group, "provider"), "")
    session.add(other_church.person)
    session.flush()
    for field, who in (
        ("successor_admin_id", other_church),
        ("successor_leader_id", scene.elsewhere),
    ):
        refused = propose(client, scene.owner, full_body(scene, **{field: str(who.person.id)}))
        assert (
            refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
        )
    bad_status = propose(client, scene.owner, full_body(scene, former_owner_status="verifier"))
    assert bad_status.status_code == 422


def test_only_the_owner_proposes_and_one_proposal_is_open(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    for who in (scene.admin, add_member(world, "provider")):
        assert propose(client, who, full_body(scene)).status_code == 403
    assert client.post(URL, json=full_body(scene)).status_code == 401
    assert propose(client, scene.owner, full_body(scene)).status_code == 201
    again = propose(client, scene.owner, full_body(scene))
    assert again.status_code == 409 and again.json()["error"]["code"] == "handover_open"
    assert len(session.scalars(select(HandoverRequest)).all()) == 1


def test_the_two_sides_see_the_open_proposal_and_nobody_else(
    client: TestClient, world: World
) -> None:
    scene = Scene(world)
    for who in (scene.owner, scene.admin):
        assert client.get(URL, headers=headers_of(client, who)).json() == {"request": None}
    created = propose(client, scene.owner, full_body(scene, former_owner_status="searcher")).json()
    for who in (scene.owner, scene.admin):
        seen = client.get(URL, headers=headers_of(client, who)).json()["request"]
        assert seen["id"] == created["id"] and seen["former_owner_status"] == "searcher"
        assert seen["new_owner"]["id"] == str(scene.admin.person.id)
        assert seen["successor_admin"]["id"] == str(scene.elsewhere.person.id)
    assert (
        client.get(URL, headers=headers_of(client, add_member(world, "provider"))).status_code
        == 403
    )


# --- accepting and cancelling -------------------------------------------------------------------


def test_only_the_chosen_admin_accepts_and_only_once(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = propose(client, scene.owner, full_body(scene)).json()["id"]
    assert (
        client.post(
            f"{URL}/{request_id}/accept", headers=headers_of(client, scene.owner)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{URL}/{request_id}/accept", headers=headers_of(client, add_member(world, "provider"))
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{URL}/00000000-0000-4000-8000-000000000000/accept",
            headers=headers_of(client, scene.admin),
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{URL}/{request_id}/accept", headers=headers_of(client, scene.admin)
        ).status_code
        == 200
    )
    again = client.post(f"{URL}/{request_id}/accept", headers=headers_of(client, scene.admin))
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_open"
    assert owners(session) == 1


def test_either_side_cancels_and_the_other_is_told(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    first = propose(client, scene.owner, full_body(scene)).json()["id"]
    assert (
        client.post(f"{URL}/{first}/cancel", headers=headers_of(client, scene.admin)).status_code
        == 204
    )
    assert "handover_cancelled" in {
        n.kind
        for n in session.scalars(
            select(Notification).where(Notification.person_id == world.owner.id)
        )
    }
    second = propose(client, scene.owner, full_body(scene)).json()["id"]
    assert (
        client.post(f"{URL}/{second}/cancel", headers=headers_of(client, scene.owner)).status_code
        == 204
    )
    assert "handover_cancelled" in {
        n.kind
        for n in session.scalars(
            select(Notification).where(Notification.person_id == scene.admin.person.id)
        )
    }
    again = client.post(f"{URL}/{second}/cancel", headers=headers_of(client, scene.owner))
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_open"
    third = propose(client, scene.owner, full_body(scene)).json()["id"]
    assert (
        client.post(
            f"{URL}/{third}/cancel", headers=headers_of(client, add_member(world, "provider"))
        ).status_code
        == 403
    )
    assert (
        client.post(f"{URL}/{third}/accept", headers=headers_of(client, scene.admin)).status_code
        == 200
    )
    late = client.post(f"{URL}/{third}/cancel", headers=headers_of(client, scene.admin))
    assert late.status_code == 409


# --- what changed since it was proposed ---------------------------------------------------------


def test_a_chosen_admin_who_is_no_longer_an_admin_cannot_accept(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = propose(client, scene.owner, full_body(scene)).json()["id"]
    session.execute(
        update(Person).where(Person.id == scene.admin.person.id).values(status="provider")
    )
    session.expire_all()
    refused = client.post(f"{URL}/{request_id}/accept", headers=headers_of(client, scene.admin))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "not_admitted"
    assert owners(session) == 1
    assert session.get(Person, world.owner.id).status == "owner"  # type: ignore[union-attr]


def test_a_proposal_of_someone_who_is_no_longer_the_owner_is_stale(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = propose(client, scene.owner, full_body(scene)).json()["id"]
    # The role moved by another way (an operator change) between the proposal and the acceptance.
    session.execute(update(Person).where(Person.id == world.owner.id).values(status="admin"))
    session.expire_all()
    refused = client.post(f"{URL}/{request_id}/accept", headers=headers_of(client, scene.admin))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "request_stale"
    assert session.get(HandoverRequest, request_id).accepted_at is None  # type: ignore[union-attr]
    assert session.get(Person, scene.admin.person.id).status == "admin"  # type: ignore[union-attr]


def test_a_successor_who_left_meanwhile_stops_the_handover_whole(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    request_id = propose(client, scene.owner, full_body(scene)).json()["id"]
    session.execute(
        update(Person)
        .where(Person.id == scene.in_group.person.id)
        .values(status="revoked", home_group_id=None, last_home_group_id=world.group.id)
    )
    session.expire_all()
    refused = client.post(f"{URL}/{request_id}/accept", headers=headers_of(client, scene.admin))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
    session.expire_all()
    assert session.get(Person, world.owner.id).status == "owner"  # type: ignore[union-attr]
    assert owners(session) == 1
    assert session.get(HandoverRequest, request_id).accepted_at is None  # type: ignore[union-attr]
    assert session.get(Church, world.church.id).admin_id == world.owner.id  # type: ignore[union-attr]


def test_the_new_kinds_are_known() -> None:
    assert {
        "handover_requested",
        "handover_cancelled",
        "owner_handed_over",
        "owner_appointed",
    } <= set(notifications.KINDS)
