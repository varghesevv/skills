"""Succession of a home group's leader: replacing, handing on, and revoking a VERIFIER."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import GroupInvitation, HomeGroup, Notification, StatusChange
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def change_leader(
    client: TestClient, who: Member, group: HomeGroup, successor: Member, former: str
) -> Any:
    return client.put(
        f"{API}/home-groups/{group.id}/leader",
        headers=headers_of(client, who),
        json={"successor_id": str(successor.person.id), "former_leader_status": former},
    )


def revoke(client: TestClient, who: Member, target: Member, successor: Member | None = None) -> Any:
    body: dict[str, Any] = {"to": "revoked"}
    if successor is not None:
        body["successor_id"] = str(successor.person.id)
    return client.put(
        f"{API}/verifier/people/{target.person.id}/status",
        headers=headers_of(client, who),
        json=body,
    )


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


def history(session: Session, who: Member) -> list[tuple[str, str | None, str]]:
    rows = session.scalars(select(StatusChange).where(StatusChange.person_id == who.person.id))
    return sorted((c.kind, c.from_status, c.to_status) for c in rows)


def second_church_admin(world: World) -> tuple[Member, HomeGroup]:
    church, group, admin = world.add_church("Hope Church")
    member = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(member.password)
    world.session.flush()
    return member, group


# --- replacing a leader -------------------------------------------------------------------------


def test_an_admin_replaces_a_leader_and_the_old_one_stays_as_a_provider(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    admitted_by_lead = add_member(world, "searcher", group=group, status_set_by_id=lead.person.id)
    client.post(f"{API}/verifier/group-invitations", headers=headers_of(client, lead))
    owner = owner_member(world)
    response = change_leader(client, owner, group, heir, "provider")
    assert response.status_code == 200, response.text
    assert response.json()["leader"] == {"id": str(heir.person.id), "name": heir.person.full_name}
    for person in (lead, heir, admitted_by_lead):
        session.refresh(person.person)
    session.refresh(group)
    assert group.leader_id == heir.person.id
    assert (heir.person.status, heir.person.status_set_by_id) == ("verifier", owner.person.id)
    assert (lead.person.status, lead.person.status_set_by_id) == ("provider", owner.person.id)
    assert lead.person.home_group_id == group.id  # they stay in the group
    assert admitted_by_lead.person.flagged_for_recheck is False  # a step-down flags nobody
    assert ("step-down", "verifier", "provider") in history(session, lead)
    assert ("appoint", "provider", "verifier") in history(session, heir)
    assert "leader_appointed" in kinds(session, heir)
    assert "leader_stepped_down" in kinds(session, lead)
    invitations = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == group.id)
    ).all()
    assert invitations and all(i.revoked_at is not None for i in invitations)
    check_rules(session)
    # The new leader leads; the old one no longer does.
    assert (
        client.get(f"{API}/verifier/applicants", headers=headers_of(client, heir)).status_code
        == 200
    )
    assert (
        client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).status_code
        == 403
    )


def test_a_pending_member_or_a_searcher_becomes_the_leader_directly(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    pending = add_member(world, "pending", group=group)
    assert change_leader(client, owner_member(world), group, pending, "searcher").status_code == 200
    session.refresh(pending.person)
    session.refresh(lead.person)
    assert pending.person.status == "verifier" and lead.person.status == "searcher"
    check_rules(session)


def test_the_successor_must_be_a_member_of_the_group(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    owner = owner_member(world)
    outsider = add_member(world, "provider")  # the first group
    revoked = add_member(world, "revoked", last_home_group_id=group.id)
    for bad in (outsider, revoked, lead):
        refused = change_leader(client, owner, group, bad, "provider")
        assert (
            refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
        )
    session.refresh(group)
    assert group.leader_id == lead.person.id  # nothing changed


def test_the_status_the_old_leader_keeps_must_fit(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    owner = owner_member(world)
    assert (
        change_leader(client, owner, group, heir, "keep").status_code == 422
    )  # a VERIFIER steps down
    own = add_member(world, "provider")  # a member of the OWNER's group
    first = world.group
    assert change_leader(client, owner, first, own, "provider").status_code == 422  # keeps status


def test_only_an_admin_of_the_church_or_the_owner(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    for who in (lead, heir, add_member(world, "searcher")):
        refused = change_leader(client, who, group, heir, "provider")
        assert refused.status_code == 403
    other, _ = second_church_admin(world)
    assert change_leader(client, other, group, heir, "provider").status_code == 404
    unknown = client.put(
        f"{API}/home-groups/00000000-0000-4000-8000-000000000000/leader",
        headers=headers_of(client, owner_member(world)),
        json={"successor_id": str(heir.person.id), "former_leader_status": "provider"},
    )
    assert unknown.status_code == 404


def test_a_closed_group_has_no_leader_to_replace(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    group.closed_at = datetime.now(UTC)
    session.flush()
    assert change_leader(client, owner_member(world), group, heir, "provider").status_code == 404


def test_a_leader_appointed_by_a_higher_leader_is_not_replaced_by_a_lower_one(
    client: TestClient, session: Session, world: World
) -> None:
    admin, _ = second_church_admin(world)
    church = session.get(HomeGroup, admin.person.home_group_id).church_id  # type: ignore[union-attr]
    vic = make_person(None, None, "verifier", church_id=church, home_group_id=None)
    group = HomeGroup(church_id=church, name="Appointed by the OWNER", leader_id=vic.id)
    session.add(group)
    session.flush()
    vic.home_group_id = group.id
    session.add(vic)
    heir = make_person(None, group, "provider", church_id=church)
    session.add(heir)
    session.add(
        StatusChange(
            person_id=vic.id,
            from_status="provider",
            to_status="verifier",
            changed_by_id=world.owner.id,
            kind="appoint",
            at=datetime.now(UTC),
        )
    )
    session.flush()
    check_rules(session)
    refused = change_leader(client, admin, group, Member(heir, ""), "provider")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "status_not_allowed"
    # The OWNER may.
    assert (
        change_leader(client, owner_member(world), group, Member(heir, ""), "provider").status_code
        == 200
    )


# --- handing on your own group ------------------------------------------------------------------


def test_the_owner_hands_on_their_own_group_and_keeps_their_status(
    client: TestClient, session: Session, world: World
) -> None:
    member = add_member(world, "provider")  # in the OWNER's group
    owner = owner_member(world)
    response = change_leader(client, owner, world.group, member, "keep")
    assert response.status_code == 200
    session.refresh(world.owner)
    session.refresh(member.person)
    session.refresh(world.group)
    assert world.owner.status == "owner" and world.owner.home_group_id == world.group.id
    assert world.group.leader_id == member.person.id and member.person.status == "verifier"
    assert history(session, owner) == []  # their status did not change
    assert "leader_stepped_down" not in kinds(session, owner)
    check_rules(session)


def test_an_admin_hands_on_only_their_own_group(
    client: TestClient, session: Session, world: World
) -> None:
    other, group = second_church_admin(world)
    heir = make_person(None, group, "provider", church_id=group.church_id)
    session.add(heir)
    session.flush()
    # The OWNER may not take over another ADMIN's group by this call.
    refused = change_leader(client, owner_member(world), group, Member(heir, ""), "keep")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "status_not_allowed"
    assert change_leader(client, other, group, Member(heir, ""), "keep").status_code == 200
    session.refresh(group)
    assert group.leader_id == heir.id
    check_rules(session)


# --- revoking a VERIFIER ------------------------------------------------------------------------


def test_revoking_a_verifier_with_a_successor_flags_those_they_admitted(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    admitted = add_member(world, "provider", group=group, status_set_by_id=lead.person.id)
    other = add_member(world, "searcher", group=group, status_set_by_id=world.owner.id)
    client.post(f"{API}/verifier/group-invitations", headers=headers_of(client, lead))
    response = revoke(client, owner_member(world), lead, heir)
    assert response.status_code == 200, response.text
    for person in (lead, heir, admitted, other):
        session.refresh(person.person)
    session.refresh(group)
    assert (lead.person.status, lead.person.home_group_id) == ("revoked", None)
    assert lead.person.last_home_group_id == group.id
    assert group.leader_id == heir.person.id and heir.person.status == "verifier"
    # Everyone the revoked leader set is flagged, keeps their status and access; nobody else is.
    assert admitted.person.flagged_for_recheck is True and admitted.person.status == "provider"
    assert other.person.flagged_for_recheck is False
    assert (
        client.get(f"{API}/me/notifications", headers=headers_of(client, admitted)).status_code
        == 200
    )
    invitations = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == group.id)
    ).all()
    assert invitations and all(i.revoked_at is not None for i in invitations)
    assert ("revoke", "verifier", "revoked") in history(session, lead)
    assert ("appoint", "provider", "verifier") in history(session, heir)
    check_rules(session)


def test_the_new_leader_reconfirms_the_flagged_people(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    heir = add_member(world, "provider", group=group)
    admitted = add_member(world, "provider", group=group, status_set_by_id=lead.person.id)
    revoke(client, owner_member(world), lead, heir)
    flagged = client.get(f"{API}/verifier/flagged", headers=headers_of(client, heir)).json()[
        "items"
    ]
    assert [r["id"] for r in flagged] == [str(admitted.person.id)]
    done = client.post(
        f"{API}/verifier/people/{admitted.person.id}/reconfirm", headers=headers_of(client, heir)
    )
    assert done.status_code == 200 and done.json()["flagged_for_recheck"] is False
    session.refresh(admitted.person)
    assert admitted.person.status_set_by_id == heir.person.id  # the new link in the chain
    check_rules(session)


def test_revoking_a_verifier_needs_a_successor_unless_they_are_alone(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    add_member(world, "provider", group=group)
    refused = revoke(client, owner_member(world), lead)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(lead.person)
    assert lead.person.status == "verifier"  # nothing changed
    alone, alone_group = leader(world)
    assert revoke(client, owner_member(world), alone).status_code == 200
    session.refresh(alone_group)
    assert alone_group.closed_at is not None  # the group closes with its only member leaving
    check_rules(session)


def test_the_successor_of_a_revoked_leader_must_belong_to_the_group(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    add_member(world, "provider", group=group)
    outsider = add_member(world, "provider")
    refused = revoke(client, owner_member(world), lead, outsider)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
    plain = add_member(world, "provider")
    wrong = revoke(client, owner_member(world), plain, outsider)
    assert wrong.status_code == 422  # only a leader has a successor


def test_an_admin_is_still_replaced_first(client: TestClient, world: World) -> None:
    # The ADMIN of a second church cannot be revoked until the church has a new ADMIN (next step).
    other, _ = second_church_admin(world)
    refused = revoke(client, owner_member(world), other)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"


def test_the_new_kinds_are_known() -> None:
    assert {"leader_appointed", "leader_stepped_down"} <= set(notifications.KINDS)


def test_a_refused_succession_leaves_the_invitation_links_alone(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    add_member(world, "provider", group=group)
    client.post(f"{API}/verifier/group-invitations", headers=headers_of(client, lead))
    outsider = add_member(world, "provider")
    for call in (
        lambda: revoke(client, owner_member(world), lead),  # no successor, members exist
        lambda: revoke(client, owner_member(world), lead, outsider),  # not a member
    ):
        assert call().status_code == 409
    links = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == group.id)
    ).all()
    assert links and all(link.revoked_at is None for link in links)


def test_joining_a_group_takes_a_shared_lock_on_it(
    client: TestClient, session: Session, world: World
) -> None:
    """Closing a group takes its row for update; a sign-up must wait for that or see the group
    closed, so a group cannot close at the moment someone joins it."""
    from sqlalchemy import event

    lead, group = leader(world)
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        statements.append(statement)

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        response = client.post(
            f"{API}/auth/signup",
            json={
                "full_name": "New Applicant",
                "email": f"applicant-{secrets.token_hex(4)}@example.com",
                "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
                "password": secrets.token_urlsafe(16),
                "requested_status": "searcher",
                "home_group_id": str(group.id),
            },
        )
    finally:
        event.remove(bind, "before_cursor_execute", record)
    assert response.status_code == 201
    assert any("home_groups" in s and "FOR SHARE" in s for s in statements)
