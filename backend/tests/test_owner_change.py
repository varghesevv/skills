"""The operators change the OWNER outside the app, with the appointments of a handover."""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import main
from app.core.security import hash_password
from app.models import Church, HandoverRequest, HomeGroup, Person, StatusChange
from app.services.operators import SetupError, change_owner
from tests.api_helpers import API
from tests.test_admission import headers_of
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


class Scene:
    """The OWNER's church with a member in their group and one in another group, and a second
    church whose ADMIN is the one the operators choose."""

    def __init__(self, world: World) -> None:
        self.world = world
        session = world.session
        self.in_group = add_member(world, "provider")
        lead = make_person(world.church, None, "verifier", home_group_id=None)
        self.other_group = HomeGroup(church_id=world.church.id, name="Harbour", leader_id=lead.id)
        session.add(self.other_group)
        session.flush()
        lead.home_group_id = self.other_group.id
        session.add(lead)
        self.elsewhere = add_member(world, "searcher", group=self.other_group)
        self.church, self.group, self.admin = world.add_church("Hope Church")
        self.password = secrets.token_urlsafe(16)
        self.admin.password_hash = hash_password(self.password)
        session.flush()
        check_rules(session)

    def email(self, member: Member | Person) -> str:
        person = member.person if isinstance(member, Member) else member
        return str(person.email)

    def run(self, **extra: Any) -> Any:
        args: dict[str, Any] = {
            "new_owner_email": self.email(self.admin),
            "admin_successor_email": self.email(self.elsewhere),
            "leader_successor_email": self.email(self.in_group),
        }
        args.update(extra)
        return change_owner(self.world.session, **args)


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


# --- changing the OWNER -------------------------------------------------------------------------


def test_the_operators_make_the_chosen_admin_the_owner_with_the_appointments(
    session: Session, world: World
) -> None:
    scene = Scene(world)
    pending = HandoverRequest(owner_id=world.owner.id, new_owner_id=scene.admin.id)
    session.add(pending)
    session.flush()
    result = scene.run(former_status="searcher")
    assert (result.old_owner_id, result.new_owner_id) == (world.owner.id, scene.admin.id)
    assert result.old_owner_status == "searcher" and result.flagged == 0
    for person in (world.owner, scene.admin, scene.elsewhere.person, scene.in_group.person):
        session.refresh(person)
    session.refresh(world.church)
    session.refresh(world.group)
    session.refresh(scene.church)
    assert scene.admin.status == "owner" and scene.church.admin_id == scene.admin.id
    assert (world.owner.status, world.owner.home_group_id) == ("searcher", world.group.id)
    assert world.church.admin_id == scene.elsewhere.person.id
    assert scene.elsewhere.person.status == "admin"
    assert world.group.leader_id == scene.in_group.person.id
    assert scene.in_group.person.status == "verifier"
    assert owners(session) == 1
    # Recorded as operator changes: no person is behind any of them.
    for person, expected in (
        (scene.admin, ("operator", "admin", "owner", None)),
        (world.owner, ("operator", "owner", "searcher", None)),
        (scene.elsewhere.person, ("operator", "searcher", "admin", None)),
        (scene.in_group.person, ("operator", "provider", "verifier", None)),
    ):
        assert expected in history(session, person)
    assert world.owner.status_set_by_id is None
    session.refresh(pending)
    assert pending.cancelled_at is not None  # a proposal of the old OWNER no longer applies
    check_rules(session)


def test_with_nobody_to_take_over_the_old_owner_keeps_the_roles(
    session: Session, world: World
) -> None:
    church, group, admin = world.add_church("Hope Church")
    result = change_owner(session, new_owner_email=str(admin.email))
    session.refresh(world.owner)
    assert world.owner.status == "admin" and result.old_owner_status == "admin"
    assert owners(session) == 1
    check_rules(session)


def test_a_breach_of_trust_revokes_the_old_owner_and_flags_those_they_set(
    client: TestClient, session: Session, world: World
) -> None:
    scene = Scene(world)
    # The old OWNER appointed the ADMIN of the second church, and a provider.
    scene.admin.status_set_by_id = world.owner.id
    set_by_owner = add_member(world, "provider", status_set_by_id=world.owner.id)
    other = add_member(world, "provider", status_set_by_id=scene.admin.id)
    session.flush()
    result = scene.run(revoke_old_owner=True)
    for person in (world.owner, scene.admin, set_by_owner.person, other.person):
        session.refresh(person)
    session.refresh(world.group)
    assert (world.owner.status, world.owner.home_group_id) == ("revoked", None)
    assert world.owner.last_home_group_id == world.group.id
    assert set_by_owner.person.flagged_for_recheck is True  # set by the revoked OWNER
    assert set_by_owner.person.status == "provider"  # and keeps their access and status
    assert other.person.flagged_for_recheck is False
    assert scene.admin.flagged_for_recheck is False  # the new OWNER is the root now
    assert result.flagged >= 1 and result.old_owner_status == "revoked"
    assert ("operator", "owner", "revoked", None) in history(session, world.owner)
    assert owners(session) == 1
    check_rules(session)
    # The new OWNER clears the flags, as any leader at the level of the revoked OWNER does.
    new_owner = Member(scene.admin, scene.password)
    listed = client.get(f"{API}/verifier/flagged", headers=headers_of(client, new_owner)).json()
    assert str(set_by_owner.person.id) in {r["id"] for r in listed["items"]}
    done = client.post(
        f"{API}/verifier/people/{set_by_owner.person.id}/reconfirm",
        headers=headers_of(client, new_owner),
    )
    assert done.status_code == 200 and done.json()["flagged_for_recheck"] is False


@pytest.mark.parametrize(
    ("field", "message"),
    [("admin_successor_email", "ADMIN"), ("leader_successor_email", "leader")],
)
def test_a_church_or_group_with_members_needs_its_successor(
    session: Session, world: World, field: str, message: str
) -> None:
    scene = Scene(world)
    # The church has other members and so does the group: each needs the person who takes over.
    with pytest.raises(SetupError, match=message):
        scene.run(**{field: None})


def test_a_revoked_owner_cannot_keep_their_church(session: Session, world: World) -> None:
    scene = Scene(world)
    with pytest.raises(SetupError, match="ADMIN"):
        scene.run(admin_successor_email=None, revoke_old_owner=True)


def test_a_revoked_owner_alone_in_their_church_cannot_keep_it_either(
    session: Session, world: World
) -> None:
    # Nobody else is in the church, so no ADMIN can be named: the old OWNER would keep it, which a
    # revoked person cannot. (Such a church is closed first.)
    _, _, admin = world.add_church("Hope Church")
    with pytest.raises(SetupError, match="cannot keep their church"):
        change_owner(session, new_owner_email=str(admin.email), revoke_old_owner=True)


def test_the_shared_operation_refuses_before_it_changes_anything(
    session: Session, world: World
) -> None:
    """A refusal comes from the checks, before any row is changed: called directly (no rollback
    to hide it), the people and the churches are as they were."""
    from app.core.errors import ApiError
    from app.services import ownership

    scene = Scene(world)
    operator_rows = session.scalar(
        select(func.count()).select_from(StatusChange).where(StatusChange.kind == "operator")
    )
    with pytest.raises(ApiError) as caught:
        ownership.transfer(
            session,
            old=world.owner,
            new=scene.admin,
            admin_successor_id=None,  # the church has other members
            leader_successor_id=None,
            former_status="provider",
            kind="operator",
        )
    assert caught.value.code == "successor_required"
    session.expire_all()
    assert session.get(Person, world.owner.id).status == "owner"  # type: ignore[union-attr]
    assert session.get(Person, scene.admin.id).status == "admin"  # type: ignore[union-attr]
    assert session.get(Church, world.church.id).admin_id == world.owner.id  # type: ignore[union-attr]
    after = session.scalar(
        select(func.count()).select_from(StatusChange).where(StatusChange.kind == "operator")
    )
    assert after == operator_rows  # no history was written
    assert owners(session) == 1


def test_a_revoked_owner_alone_in_their_group_closes_it(session: Session, world: World) -> None:
    scene = Scene(world)
    session.execute(
        Person.__table__.update()
        .where(Person.id == scene.in_group.person.id)
        .values(home_group_id=scene.other_group.id)
    )
    session.expire_all()
    scene.run(leader_successor_email=None, revoke_old_owner=True)
    session.refresh(world.group)
    assert world.group.closed_at is not None
    check_rules(session)


# --- what is refused ----------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["a member", "the OWNER", "nobody"])
def test_the_chosen_must_be_the_admin_of_another_church(
    session: Session, world: World, who: str
) -> None:
    scene = Scene(world)
    chosen = {
        "a member": scene.email(scene.in_group),  # not an ADMIN
        "the OWNER": scene.email(world.owner),  # the OWNER themselves
        "nobody": "nobody@example.com",  # no such account
    }[who]
    with pytest.raises(SetupError):
        scene.run(new_owner_email=chosen)


@pytest.mark.parametrize("what", ["other church", "other group", "bad status"])
def test_the_successors_must_belong_and_the_status_must_fit(
    session: Session, world: World, what: str
) -> None:
    scene = Scene(world)
    stranger = make_person(scene.church, scene.group, "provider")
    session.add(stranger)
    session.flush()
    kwargs: dict[str, Any] = {
        "other church": {"admin_successor_email": scene.email(stranger)},
        "other group": {"leader_successor_email": scene.email(scene.elsewhere)},
        "bad status": {"former_status": "verifier"},
    }[what]
    with pytest.raises(SetupError):
        scene.run(**kwargs)


def test_the_command_needs_the_new_owner() -> None:
    with pytest.raises(SystemExit):
        main(["change-owner"])  # --new-owner is required
