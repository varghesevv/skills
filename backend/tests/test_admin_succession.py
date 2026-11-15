"""Succession of a church's ADMIN: replacing one, and revoking one."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Church, GroupInvitation, HomeGroup, Notification, Person, StatusChange
from app.services import notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, owner_member
from tests.test_person_auth import Member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


class Second:
    """A second church: its ADMIN leads the first group; `member` is another person in it."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.church, self.group, admin = world.add_church("Hope Church")
        password = secrets.token_urlsafe(16)
        admin.password_hash = hash_password(password)
        self.admin = Member(admin, password)
        world.session.flush()

    def person(self, status: str, group: HomeGroup | None = None, **extra: Any) -> Member:
        person = make_person(self.church, group or self.group, status, **extra)
        person.password_hash = hash_password("unused-" + secrets.token_hex(6))
        self.world.session.add(person)
        self.world.session.flush()
        return Member(person, "")

    def second_group(self, name: str = "Harbour") -> tuple[Member, HomeGroup]:
        """A VERIFIER leading a group of their own in this church."""
        lead = make_person(self.church, None, "verifier", home_group_id=None)
        group = HomeGroup(church_id=self.church.id, name=name, leader_id=lead.id)
        session = self.world.session
        session.add(group)
        session.flush()
        lead.home_group_id = group.id
        session.add(lead)
        session.flush()
        check_rules(session)
        return Member(lead, ""), group


def replace(
    client: TestClient,
    who: Member,
    church: Church,
    successor: Member,
    former: str = "provider",
    group_successor: Member | None = None,
) -> Any:
    body: dict[str, Any] = {"successor_id": str(successor.person.id), "former_admin_status": former}
    if group_successor is not None:
        body["group_successor_id"] = str(group_successor.person.id)
    return client.put(
        f"{API}/churches/{church.id}/admin", headers=headers_of(client, who), json=body
    )


def revoke(
    client: TestClient,
    who: Member,
    target: Member,
    successor: Member | None = None,
    group_successor: Member | None = None,
) -> Any:
    body: dict[str, Any] = {"to": "revoked"}
    if successor is not None:
        body["successor_id"] = str(successor.person.id)
    if group_successor is not None:
        body["group_successor_id"] = str(group_successor.person.id)
    return client.put(
        f"{API}/verifier/people/{target.person.id}/status",
        headers=headers_of(client, who),
        json=body,
    )


def history(session: Session, who: Member) -> list[tuple[str, str | None, str]]:
    rows = session.scalars(select(StatusChange).where(StatusChange.person_id == who.person.id))
    return sorted((c.kind, c.from_status, c.to_status) for c in rows)


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


# --- replacing an ADMIN -------------------------------------------------------------------------


def test_the_owner_replaces_an_admin_who_is_alone_in_their_group(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    _, other_group = second.second_group()
    heir = second.person("provider", other_group)
    owner = owner_member(world)
    response = replace(client, owner, second.church, heir)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["admin"]["id"] == str(heir.person.id)
    assert body["former_admin_keeps_leading"] is True  # alone in their group: they keep leading it
    for person in (second.admin, heir):
        session.refresh(person.person)
    session.refresh(second.church)
    session.refresh(second.group)
    assert second.church.admin_id == heir.person.id and heir.person.status == "admin"
    assert heir.person.status_set_by_id == owner.person.id
    assert second.admin.person.status == "verifier"  # nobody can lead the group in their place
    assert second.group.leader_id == second.admin.person.id
    assert ("appoint", "provider", "admin") in history(session, heir)
    assert ("step-down", "admin", "verifier") in history(session, second.admin)
    assert "admin_appointed" in kinds(session, heir) and "admin_stepped_down" in kinds(
        session, second.admin
    )
    check_rules(session)
    # The new ADMIN decides group requests of the church; the old one no longer does.
    assert (
        client.get(f"{API}/group-requests", headers=headers_of(client, second.admin)).status_code
        == 200
    )
    me = client.get(f"{API}/me", headers=headers_of(client, second.admin)).json()
    assert me["status"] == "verifier"


def test_the_group_of_the_old_admin_passes_to_a_member_and_they_become_a_provider(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    _, other_group = second.second_group()
    heir = second.person("searcher", other_group)
    keeper = second.person("provider")  # a member of the old ADMIN's group
    client.post(f"{API}/verifier/group-invitations", headers=headers_of(client, second.admin))
    refused = replace(client, owner_member(world), second.church, heir)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_required"
    session.refresh(second.church)
    assert second.church.admin_id == second.admin.person.id  # nothing changed
    done = replace(client, owner_member(world), second.church, heir, "searcher", keeper)
    assert done.status_code == 200 and done.json()["former_admin_keeps_leading"] is False
    for person in (second.admin, keeper, heir):
        session.refresh(person.person)
    session.refresh(second.group)
    assert second.admin.person.status == "searcher"
    assert (second.group.leader_id, keeper.person.status) == (keeper.person.id, "verifier")
    assert second.admin.person.home_group_id == second.group.id  # they stay in their group
    links = session.scalars(
        select(GroupInvitation).where(GroupInvitation.home_group_id == second.group.id)
    ).all()
    assert links and all(link.revoked_at is not None for link in links)
    check_rules(session)


def test_the_new_admin_may_also_take_the_group(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    heir = second.person("provider")  # a member of the old ADMIN's own group
    done = replace(client, owner_member(world), second.church, heir, "provider", heir)
    assert done.status_code == 200, done.text
    session.refresh(heir.person)
    session.refresh(second.group)
    assert heir.person.status == "admin" and second.group.leader_id == heir.person.id
    # One promotion, not two.
    assert [h for h in history(session, heir) if h[0] == "appoint"] == [
        ("appoint", "provider", "admin")
    ]
    check_rules(session)


def test_a_successor_who_leads_a_group_keeps_leading_it(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    lead, group = second.second_group()
    keeper = second.person("provider")
    done = replace(client, owner_member(world), second.church, lead, "provider", keeper)
    assert done.status_code == 200, done.text
    session.refresh(lead.person)
    session.refresh(group)
    assert lead.person.status == "admin" and group.leader_id == lead.person.id
    check_rules(session)


def test_the_successors_must_belong_where_they_are_named(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    owner = owner_member(world)
    outsider = Member(make_person(world.church, world.group, "provider"), "")
    world.session.add(outsider.person)
    session.flush()
    revoked = second.person("revoked", None, last_home_group_id=second.group.id)
    for bad in (outsider, revoked, second.admin, Member(world.owner, "")):
        refused = replace(client, owner, second.church, bad)
        assert (
            refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
        )
    heir = second.person("provider")
    stranger = second.person("provider", second.second_group()[1])
    bad_group = replace(client, owner, second.church, heir, "provider", stranger)
    assert (
        bad_group.status_code == 409 and bad_group.json()["error"]["code"] == "successor_not_member"
    )
    # Nothing is half done: read through queries (which flush anything pending).
    admin_id = session.scalar(select(Church.admin_id).where(Church.id == second.church.id))
    assert admin_id == second.admin.person.id
    assert session.scalar(select(Person.status).where(Person.id == heir.person.id)) == "provider"


def test_a_group_successor_is_for_an_admin_who_leads(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    keeper = second.person("provider")
    heir = second.person("provider")
    # The ADMIN hands their group on first.
    assert (
        client.put(
            f"{API}/home-groups/{second.group.id}/leader",
            headers=headers_of(client, second.admin),
            json={"successor_id": str(keeper.person.id), "former_leader_status": "keep"},
        ).status_code
        == 200
    )
    refused = replace(client, owner_member(world), second.church, heir, "provider", keeper)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "invalid_choice"
    assert replace(client, owner_member(world), second.church, heir).status_code == 200
    session.refresh(second.admin.person)
    assert second.admin.person.status == "provider"  # they led nothing: no group to keep
    check_rules(session)


def test_only_the_owner_and_not_for_their_own_church(client: TestClient, world: World) -> None:
    second = Second(world)
    heir = second.person("provider")
    refused = replace(client, second.admin, second.church, heir)
    assert refused.status_code == 403
    own = replace(client, owner_member(world), world.church, heir)
    assert own.status_code == 409 and own.json()["error"]["code"] == "owner_church"
    unknown = client.put(
        f"{API}/churches/00000000-0000-4000-8000-000000000000/admin",
        headers=headers_of(client, owner_member(world)),
        json={"successor_id": str(heir.person.id), "former_admin_status": "provider"},
    )
    assert unknown.status_code == 404


def test_a_closed_church_has_no_admin_to_replace(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    heir = second.person("provider")
    second.church.closed_at = datetime.now(UTC)
    session.flush()
    assert replace(client, owner_member(world), second.church, heir).status_code == 404


def test_the_old_admin_must_be_able_to_step_down(client: TestClient, world: World) -> None:
    second = Second(world)
    heir = second.person("provider")
    body = {"successor_id": str(heir.person.id), "former_admin_status": "keep"}
    response = client.put(
        f"{API}/churches/{second.church.id}/admin",
        headers=headers_of(client, owner_member(world)),
        json=body,
    )
    assert response.status_code == 422


# --- revoking an ADMIN --------------------------------------------------------------------------


def test_revoking_an_admin_replaces_them_closes_their_lone_group_and_flags_those_they_set(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    _, elsewhere = second.second_group()  # everyone else belongs to this group, so the ADMIN is
    heir = second.person("provider", elsewhere)  # alone in the group they lead
    set_by_admin = second.person("provider", elsewhere, status_set_by_id=second.admin.person.id)
    other = second.person("provider", elsewhere, status_set_by_id=world.owner.id)
    response = revoke(client, owner_member(world), second.admin, heir)
    assert response.status_code == 200, response.text
    for person in (second.admin, heir, set_by_admin, other):
        session.refresh(person.person)
    session.refresh(second.church)
    session.refresh(second.group)
    assert second.admin.person.status == "revoked" and second.admin.person.home_group_id is None
    assert second.admin.person.last_home_group_id == second.group.id
    assert second.church.admin_id == heir.person.id and heir.person.status == "admin"
    assert second.group.closed_at is not None  # they were alone in it
    # Everyone the revoked ADMIN set is flagged and keeps their status; nobody else is.
    assert (
        set_by_admin.person.flagged_for_recheck is True and set_by_admin.person.status == "provider"
    )
    assert other.person.flagged_for_recheck is False
    assert ("revoke", "admin", "revoked") in history(session, second.admin)
    check_rules(session)


def test_the_new_admin_reconfirms_the_flagged_people(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    _, elsewhere = second.second_group()
    heir = second.person("provider", elsewhere)
    flagged = second.person("provider", elsewhere, status_set_by_id=second.admin.person.id)
    assert revoke(client, owner_member(world), second.admin, heir).status_code == 200
    password = secrets.token_urlsafe(16)
    heir.person.password_hash = hash_password(password)
    session.flush()
    new_admin = Member(heir.person, password)
    listed = client.get(f"{API}/verifier/flagged", headers=headers_of(client, new_admin)).json()[
        "items"
    ]
    assert [r["id"] for r in listed] == [str(flagged.person.id)]
    done = client.post(
        f"{API}/verifier/people/{flagged.person.id}/reconfirm",
        headers=headers_of(client, new_admin),
    )
    assert done.status_code == 200 and done.json()["flagged_for_recheck"] is False
    check_rules(session)


def test_revoking_an_admin_needs_a_church_successor_and_a_group_successor(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    heir = second.person("provider", second.second_group()[1])
    keeper = second.person("provider")  # in the ADMIN's own group
    owner = owner_member(world)
    no_church = revoke(client, owner, second.admin)
    assert (
        no_church.status_code == 409 and no_church.json()["error"]["code"] == "successor_required"
    )
    no_group = revoke(client, owner, second.admin, heir)  # their group has another member
    assert no_group.status_code == 409 and no_group.json()["error"]["code"] == "successor_required"
    session.refresh(second.admin.person)
    assert second.admin.person.status == "admin"  # nothing changed
    done = revoke(client, owner, second.admin, heir, keeper)
    assert done.status_code == 200, done.text
    session.refresh(second.group)
    session.refresh(keeper.person)
    assert second.group.closed_at is None and second.group.leader_id == keeper.person.id
    check_rules(session)


def test_only_the_owner_revokes_an_admin_and_a_successor_belongs_to_a_leader(
    client: TestClient, world: World
) -> None:
    second = Second(world)
    heir = second.person("provider")
    plain = second.person("provider")
    # An ADMIN of another church or a leader of a group has no authority over this ADMIN.
    assert revoke(client, second.admin, second.admin, heir).status_code == 404  # oneself
    wrong = revoke(client, owner_member(world), plain, heir)
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "invalid_choice"
    wrong_group = revoke(client, owner_member(world), plain, None, heir)
    assert wrong_group.status_code == 422


def test_the_new_kinds_are_known() -> None:
    assert {"admin_appointed", "admin_stepped_down"} <= set(notifications.KINDS)


@pytest.mark.parametrize("caller", ["anonymous", "verifier", "provider", "searcher", "pending"])
def test_nobody_but_the_owner_may_replace_an_admin(
    client: TestClient, world: World, caller: str
) -> None:
    second = Second(world)
    heir = second.person("provider")
    body = {"successor_id": str(heir.person.id), "former_admin_status": "provider"}
    url = f"{API}/churches/{second.church.id}/admin"
    if caller == "anonymous":
        assert client.put(url, json=body).status_code == 401
        return
    who = second.second_group()[0] if caller == "verifier" else second.person(caller)
    who.person.password_hash = hash_password("x" + secrets.token_hex(8))
    password = secrets.token_urlsafe(16)
    who.person.password_hash = hash_password(password)
    world.session.flush()
    response = client.put(url, headers=headers_of(client, Member(who.person, password)), json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_admitted"


def test_one_person_never_leads_two_groups_through_a_succession(
    client: TestClient, session: Session, world: World
) -> None:
    second = Second(world)
    lead, group = second.second_group()  # a VERIFIER who leads another group
    keeper = second.person("provider")  # in the ADMIN's own group
    # The new ADMIN already leads a group; naming them for the old ADMIN's group too would give
    # them two. They do not belong to that group, so they cannot be its successor.
    refused = replace(client, owner_member(world), second.church, lead, "provider", lead)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "successor_not_member"
    admin_id = session.scalar(select(Church.admin_id).where(Church.id == second.church.id))
    assert admin_id == second.admin.person.id  # nothing changed
    assert (
        session.scalar(select(HomeGroup.leader_id).where(HomeGroup.id == group.id))
        == lead.person.id
    )
    # Another member can take it.
    assert (
        replace(client, owner_member(world), second.church, lead, "provider", keeper).status_code
        == 200
    )
    check_rules(session)
