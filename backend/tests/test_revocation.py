"""Revoking, reinstating and re-confirming people, and the re-check flags."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import HomeGroup, Notification, Person, StatusChange, Vouch, VouchLink
from app.services import notifications, revocation
from tests.api_helpers import API
from tests.test_admission import add_vouch, headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db

V = f"{API}/verifier"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def set_status(
    client: TestClient, who: Member, target: Member, to: str, group: HomeGroup | None = None
) -> Any:
    body: dict[str, Any] = {"to": to}
    if group is not None:
        body["home_group_id"] = str(group.id)
    return client.put(
        f"{V}/people/{target.person.id}/status", headers=headers_of(client, who), json=body
    )


def reconfirm(client: TestClient, who: Member, target: Member) -> Any:
    return client.post(f"{V}/people/{target.person.id}/reconfirm", headers=headers_of(client, who))


def history(session: Session, person: Member) -> list[StatusChange]:
    return list(
        session.scalars(
            select(StatusChange)
            .where(StatusChange.person_id == person.person.id)
            .order_by(StatusChange.at)
        )
    )


def kinds(session: Session, person: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == person.person.id))
    return sorted(n.kind for n in rows)


def admin_member(world: World) -> Member:
    """The ADMIN of a second church, with a password (the first church's ADMIN is the OWNER)."""
    _, _, admin = world.add_church()
    member = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(member.password)
    world.session.flush()
    return member


# --- revoking -----------------------------------------------------------------------------------


def test_a_leader_revokes_a_member_of_their_group(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group)
    link = VouchLink(
        person_id=member.person.id,
        token_hash=secrets.token_hex(16),
        expires_at=datetime(2100, 1, 1, tzinfo=UTC),
    )
    session.add(link)
    session.flush()
    response = set_status(client, lead, member, "revoked")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(member.person.id),
        "status": "revoked",
        "home_group_id": None,
        "flagged_for_recheck": False,
    }
    session.refresh(member.person)
    person = member.person
    assert (person.status, person.home_group_id) == ("revoked", None)
    assert person.last_home_group_id == group.id  # the group they were removed from
    assert person.status_set_by_id == lead.person.id
    change = history(session, member)[-1]
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "revoke",
        "provider",
        "revoked",
        lead.person.id,
    )
    session.refresh(link)
    assert link.revoked_at is not None
    assert "revoked" in kinds(session, member)
    check_rules(session)


def test_a_revoked_person_keeps_their_login_but_loses_access(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group)
    set_status(client, lead, member, "revoked")
    headers = headers_of(client, member)  # they can still sign in (decision D-15)
    assert client.get(f"{API}/me", headers=headers).json()["status"] == "revoked"
    blocked = client.get(f"{API}/me/vouches-given", headers=headers)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "account_revoked"
    revoked = client.get(f"{V}/revoked", headers=headers_of(client, lead)).json()["items"]
    assert [r["id"] for r in revoked] == [str(member.person.id)]
    assert revoked[0]["revoked_by"] == {"name": lead.person.full_name}
    assert revoked[0]["removed_from"]["id"] == str(group.id)


def test_their_vouches_stop_counting_for_applicants_still_pending(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group, requested_status="provider")
    voucher = add_member(world, "provider", group=group)
    add_vouch(world, applicant, voucher)
    count = lambda: client.get(  # noqa: E731
        f"{API}/me", headers=headers_of(client, applicant)
    ).json()["vouch_count"]
    assert count() == 1
    set_status(client, lead, voucher, "revoked")
    assert count() == 0


def test_a_pending_applicant_can_be_revoked_too(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group, requested_status="provider")
    assert set_status(client, lead, applicant, "revoked").status_code == 200
    assert applicant.person.requested_status is None


def test_nobody_revokes_outside_their_scope_or_themselves(client: TestClient, world: World) -> None:
    lead, _ = leader(world)
    elsewhere = add_member(world, "provider")  # the first group
    assert set_status(client, lead, elsewhere, "revoked").status_code == 404
    assert set_status(client, lead, lead, "revoked").status_code == 404


def test_only_leaders_use_it(client: TestClient, world: World) -> None:
    target = add_member(world, "searcher")
    for status in ("pending", "searcher", "provider"):
        response = set_status(client, add_member(world, status), target, "revoked")
        assert response.status_code == 403 and response.json()["error"]["code"] == "not_admitted"


def test_a_leader_with_members_is_replaced_first(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    add_member(world, "provider", group=group)  # the group has another member
    refused = set_status(client, owner_member(world), lead, "revoked")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(lead.person)
    assert lead.person.status == "verifier" and lead.person.home_group_id == group.id
    # The succession itself is tested in tests/test_succession.py.


def test_a_leader_cannot_revoke_a_peer_or_the_owner(client: TestClient, world: World) -> None:
    lead, _ = leader(world)
    other_lead, _ = leader(world)
    # Out of scope: the other leader's group is not theirs, and the OWNER is in the first group.
    assert set_status(client, lead, other_lead, "revoked").status_code == 404
    assert set_status(client, lead, Member(world.owner, "x"), "revoked").status_code == 404


def test_the_owner_cannot_be_revoked_through_the_app(client: TestClient, world: World) -> None:
    admin = admin_member(world)
    owner = Member(world.owner, "unused")
    # The OWNER is in the first church; a second church's ADMIN has no authority there (404), and
    # a person cannot revoke themselves.
    assert set_status(client, admin, owner, "revoked").status_code == 404
    assert set_status(client, owner_member(world), owner, "revoked").status_code == 404


def test_revoking_twice_is_refused(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group)
    assert set_status(client, lead, member, "revoked").status_code == 200
    again = set_status(client, lead, member, "revoked")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_revoked"


def test_other_changes_of_status_are_not_made_here(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group)
    # A demotion is not a revocation or a reinstatement: the person is not revoked.
    response = set_status(client, lead, member, "searcher", group)
    assert response.status_code == 409 and response.json()["error"]["code"] == "not_revoked"
    # Setting a leader's status is not done here at all, and a revocation takes no group.
    for body in ({"to": "verifier"}, {"to": "revoked", "home_group_id": str(group.id)}):
        assert (
            client.put(
                f"{V}/people/{member.person.id}/status",
                headers=headers_of(client, lead),
                json=body,
            ).status_code
            == 422
        )
    assert (
        client.put(
            f"{V}/people/{member.person.id}/status",
            headers=headers_of(client, lead),
            json={"to": "searcher"},
        ).status_code
        == 422
    )  # reinstating needs a home group


# --- reinstating --------------------------------------------------------------------------------


def revoked_member(
    client: TestClient, world: World, lead: Member, group: HomeGroup, status: str = "provider"
) -> Member:
    member = add_member(world, status, group=group)
    assert set_status(client, lead, member, "revoked").status_code == 200
    return member


def test_a_leader_reinstates_who_they_revoked(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = revoked_member(client, world, lead, group)
    response = set_status(client, lead, member, "searcher", group)
    assert response.status_code == 200
    assert response.json()["status"] == "searcher"
    assert response.json()["home_group_id"] == str(group.id)
    session.refresh(member.person)
    assert member.person.last_home_group_id is None
    assert member.person.status_set_by_id == lead.person.id
    change = history(session, member)[-1]
    assert (change.kind, change.from_status, change.to_status) == (
        "reinstate",
        "revoked",
        "searcher",
    )
    assert kinds(session, member) == ["reinstated", "revoked"]
    assert {"revoked", "reinstated"} <= set(notifications.KINDS)
    # They are back: the screens for their status work again.
    assert (
        client.get(f"{API}/me/notifications", headers=headers_of(client, member)).status_code == 200
    )
    check_rules(session)


def test_reinstating_needs_a_group_in_the_church_that_is_open(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = revoked_member(client, world, lead, group)
    missing = client.put(
        f"{V}/people/{member.person.id}/status",
        headers=headers_of(client, lead),
        json={"to": "searcher"},
    )
    assert missing.status_code == 422
    _, other_church_group, _ = world.add_church("Elsewhere")
    assert set_status(client, lead, member, "searcher", other_church_group).status_code == 422
    closed = world.add_group(add_member(world, "provider").person, "Closed soon")
    closed.closed_at = datetime.now(UTC)
    session.flush()
    admin = owner_member(world)
    assert set_status(client, admin, member, "searcher", closed).status_code == 422


def test_a_leader_places_them_only_in_their_own_group(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = revoked_member(client, world, lead, group)
    elsewhere = world.group
    refused = set_status(client, lead, member, "searcher", elsewhere)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "status_not_allowed"
    # The OWNER may place them in any group of the church.
    assert set_status(client, owner_member(world), member, "searcher", elsewhere).status_code == 200


def test_a_revocation_by_a_higher_leader_cannot_be_undone_by_a_lower_one(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group)
    owner = owner_member(world)
    assert set_status(client, owner, member, "revoked").status_code == 200
    refused = set_status(client, lead, member, "searcher", group)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "status_not_allowed"
    assert set_status(client, owner, member, "searcher", group).status_code == 200


def test_a_higher_leader_can_undo_a_lower_ones_revocation(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = revoked_member(client, world, lead, group)
    assert set_status(client, owner_member(world), member, "provider", group).status_code == 200


def test_only_a_revoked_person_is_reinstated(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group)
    assert (
        set_status(client, lead, member, "searcher", group).json()["error"]["code"] == "not_revoked"
    )


def test_a_revoked_person_can_not_sign_up_again(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = revoked_member(client, world, lead, group)
    response = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Back Again",
            "email": member.email,
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(group.id),
        },
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "account_exists"


# --- flags and re-confirming --------------------------------------------------------------------


def ex_leader(world: World, group: HomeGroup, level: str) -> Person:
    """A person who was revoked as a leader of `level` (with the history row that says so)."""
    gone = world.add_person("revoked", last_home_group_id=group.id)
    world.session.add(
        StatusChange(
            person_id=gone.id,
            from_status=level,
            to_status="revoked",
            changed_by_id=world.owner.id,
            kind="revoke",
            at=datetime.now(UTC),
        )
    )
    world.session.flush()
    return gone


def test_everyone_a_revoked_leader_set_is_flagged_and_keeps_access(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    gone = ex_leader(world, group, "verifier")
    first = add_member(world, "provider", group=group, status_set_by_id=gone.id)
    second = add_member(world, "searcher", group=group, status_set_by_id=gone.id)
    unrelated = add_member(world, "provider", group=group, status_set_by_id=lead.person.id)
    already_out = world.add_person("revoked", last_home_group_id=group.id, status_set_by_id=gone.id)
    flagged = revocation.flag_people_set_by(session, gone)
    session.flush()
    assert flagged == 2
    for person in (first, second):
        session.refresh(person.person)
        assert person.person.flagged_for_recheck is True
        assert person.person.status in ("provider", "searcher")  # statuses do not change
    session.refresh(unrelated.person)
    session.refresh(already_out)
    assert (
        unrelated.person.flagged_for_recheck is False and already_out.flagged_for_recheck is False
    )
    # They keep their access, and the leader sees them first on the flagged list.
    assert (
        client.get(f"{API}/me/notifications", headers=headers_of(client, first)).status_code == 200
    )
    listed = client.get(f"{V}/flagged", headers=headers_of(client, lead)).json()["items"]
    assert {r["id"] for r in listed} == {str(first.person.id), str(second.person.id)}


def test_a_leader_reconfirms_a_flagged_person_and_becomes_their_new_link(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    gone = ex_leader(world, group, "verifier")
    member = add_member(
        world, "provider", group=group, status_set_by_id=gone.id, flagged_for_recheck=True
    )
    response = reconfirm(client, lead, member)
    assert response.status_code == 200
    assert response.json()["flagged_for_recheck"] is False
    session.refresh(member.person)
    assert member.person.flagged_for_recheck is False
    assert member.person.status_set_by_id == lead.person.id
    change = history(session, member)[-1]
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "reconfirm",
        "provider",
        "provider",
        lead.person.id,
    )
    assert client.get(f"{V}/flagged", headers=headers_of(client, lead)).json()["items"] == []
    page = client.get(f"{V}/people/{member.person.id}", headers=headers_of(client, lead)).json()
    assert [link["full_name"] for link in page["chain_of_trust"]][0] == lead.person.full_name
    check_rules(session)


def test_a_person_set_by_a_revoked_admin_needs_a_leader_at_that_level(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    gone = ex_leader(world, group, "admin")
    member = add_member(
        world, "provider", group=group, status_set_by_id=gone.id, flagged_for_recheck=True
    )
    refused = reconfirm(client, lead, member)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "status_not_allowed"
    assert reconfirm(client, owner_member(world), member).status_code == 200


def test_reconfirming_needs_a_flag_and_scope(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    plain = add_member(world, "provider", group=group)
    refused = reconfirm(client, lead, plain)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_flagged"
    elsewhere = add_member(world, "provider", flagged_for_recheck=True)  # the first group
    assert reconfirm(client, lead, elsewhere).status_code == 404
    searcher = add_member(world, "searcher")
    assert reconfirm(client, searcher, plain).status_code == 403


def test_revoking_clears_the_persons_own_flag(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group, flagged_for_recheck=True)
    assert set_status(client, lead, member, "revoked").json()["flagged_for_recheck"] is False


def test_revoking_changes_nobody_elses_status(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group)
    admitted_by_member = add_member(
        world, "searcher", group=group, status_set_by_id=member.person.id
    )
    set_status(client, lead, member, "revoked")
    session.refresh(admitted_by_member.person)
    assert admitted_by_member.person.status == "searcher"
    assert admitted_by_member.person.flagged_for_recheck is False  # a provider is not a leader
    assert session.scalars(select(Vouch)).first() is None
    session.execute(update(Person).where(Person.id == member.person.id).values(full_name="Kept"))
