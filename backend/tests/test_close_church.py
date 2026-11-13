"""Closing a church: its groups and its members' accounts close with it, and nobody is revoked."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Church,
    GroupInvitation,
    GroupRequest,
    HomeGroup,
    MoveRequest,
    Person,
    StatusChange,
    Vouch,
    VouchLink,
)
from tests.api_helpers import API
from tests.test_admission import headers_of, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules, make_person

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


class Hope:
    """A second church: its ADMIN leads one group, a VERIFIER another, and it has members, an
    applicant and a revoked person."""

    def __init__(self, world: World, members: int = 2) -> None:
        self.world = world
        session = world.session
        self.church, self.group, self.admin = world.add_church("Hope Church")
        lead = make_person(self.church, None, "verifier", home_group_id=None)
        self.group2 = HomeGroup(church_id=self.church.id, name="Harbour", leader_id=lead.id)
        session.add(self.group2)
        session.flush()
        lead.home_group_id = self.group2.id
        session.add(lead)
        self.lead = lead
        self.people: list[Person] = []
        for n in range(members):
            self.people.append(self._add("provider" if n % 2 else "searcher", self.group))
        self.applicant = self._add("pending", self.group2, requested_status="provider")
        self.revoked = self._add("revoked", None, last_home_group_id=self.group.id)
        session.flush()
        check_rules(session)

    def _add(self, status: str, group: HomeGroup | None, **extra: Any) -> Person:
        person = make_person(self.church, group, status, **extra)
        self.world.session.add(person)
        self.world.session.flush()
        return person

    def everyone_open(self) -> list[Person]:
        return [self.admin, self.lead, *self.people, self.applicant]


def close(client: TestClient, world: World, church: Church) -> Any:
    return client.post(
        f"{API}/owner/churches/{church.id}/close", headers=headers_of(client, owner_member(world))
    )


def test_the_owner_closes_a_church_and_everything_in_it(
    client: TestClient, session: Session, world: World
) -> None:
    hope = Hope(world)
    first_church_member = add_member(world, "provider")
    statuses = {p.id: p.status for p in hope.everyone_open()}
    admin_password = secrets.token_urlsafe(16)
    hope.admin.password_hash = hash_password(admin_password)
    # Things that must end: a link of the applicant, a group link, an open move, an open request.
    session.add(
        VouchLink(
            person_id=hope.applicant.id,
            token_hash=secrets.token_hex(16),
            expires_at=datetime(2100, 1, 1, tzinfo=UTC),
        )
    )
    session.add(
        GroupInvitation(
            home_group_id=hope.group.id,
            created_by_id=hope.admin.id,
            token_hash=secrets.token_hex(16),
            expires_at=datetime(2100, 1, 1, tzinfo=UTC),
        )
    )
    move = MoveRequest(
        person_id=hope.people[0].id, from_group_id=hope.group.id, to_group_id=hope.group2.id
    )
    request = GroupRequest(
        requester_id=hope.people[1].id, church_id=hope.church.id, group_name="Lakeside"
    )
    session.add_all([move, request])
    session.flush()
    response = close(client, world, hope.church)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["closed_groups"], body["closed_accounts"]) == (
        "Hope Church",
        2,
        len(hope.everyone_open()),
    )
    session.expire_all()
    assert session.get(Church, hope.church.id).closed_at is not None  # type: ignore[union-attr]
    for group in (hope.group, hope.group2):
        assert session.get(HomeGroup, group.id).closed_at is not None  # type: ignore[union-attr]
    for person in hope.everyone_open():
        row = session.get(Person, person.id)
        assert row is not None and row.closed_at is not None  # kept, not deleted
        assert row.full_name is None and row.email is None and row.mobile_number is None
        assert row.home_group_id is None and row.flagged_for_recheck is False
        assert row.status == statuses[person.id]  # nobody is revoked or changed
    # The revoked person is untouched: still revoked, still blocking their address.
    revoked = session.get(Person, hope.revoked.id)
    assert revoked is not None and revoked.closed_at is None and revoked.status == "revoked"
    assert revoked.email == hope.revoked.email
    blocked = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Back Again",
            "email": revoked.email,
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(world.group.id),
        },
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "account_exists"
    # Links, moves and requests ended.
    assert session.scalars(select(VouchLink)).one().revoked_at is not None
    assert session.scalars(select(GroupInvitation)).one().revoked_at is not None
    assert session.get(MoveRequest, move.id).cancelled_at is not None  # type: ignore[union-attr]
    decided = session.get(GroupRequest, request.id)
    assert decided is not None and decided.state == "declined"
    assert decided.decided_by_id == world.owner.id
    # No history was written: closing a church is not a change of status.
    assert session.scalars(select(StatusChange).where(StatusChange.kind == "revoke")).all() == []
    # Nobody can sign in to the closed accounts, or join the closed groups, and the church is gone
    # from the public lists; the other church is untouched.
    login = client.post(
        f"{API}/auth/login", json={"email": "gone@example.com", "password": admin_password}
    )
    assert login.status_code == 401
    assert str(hope.church.id) not in {
        c["id"] for c in client.get(f"{API}/churches").json()["items"]
    }
    session.refresh(first_church_member.person)
    assert first_church_member.person.closed_at is None
    check_rules(session)


def test_vouches_of_the_closed_stop_counting(
    client: TestClient, session: Session, world: World
) -> None:
    hope = Hope(world)
    applicant = add_member(world, "pending", requested_status="provider")
    session.add(Vouch(applicant_id=applicant.person.id, voucher_id=hope.people[0].id))
    session.flush()
    me = lambda: client.get(  # noqa: E731
        f"{API}/me", headers=headers_of(client, applicant)
    ).json()["vouch_count"]
    assert me() == 1
    assert close(client, world, hope.church).status_code == 200
    assert me() == 0
    assert session.scalars(select(Vouch)).one()  # the vouch stays on record


def test_the_revoked_list_of_a_closed_church_is_kept(
    client: TestClient, session: Session, world: World
) -> None:
    hope = Hope(world)
    assert close(client, world, hope.church).status_code == 200
    listed = client.get(
        f"{API}/verifier/revoked", headers=headers_of(client, owner_member(world))
    ).json()["items"]
    row = next(r for r in listed if r["id"] == str(hope.revoked.id))
    assert row["removed_from"]["id"] == str(hope.group.id)


def test_not_the_owners_own_church_and_only_the_owner(
    client: TestClient, session: Session, world: World
) -> None:
    hope = Hope(world)
    own = close(client, world, world.church)
    assert own.status_code == 409 and own.json()["error"]["code"] == "owner_church"
    assert session.get(Church, world.church.id).closed_at is None  # type: ignore[union-attr]
    unknown = client.post(
        f"{API}/owner/churches/00000000-0000-4000-8000-000000000000/close",
        headers=headers_of(client, owner_member(world)),
    )
    assert unknown.status_code == 404
    for who in (add_member(world, "provider"), add_member(world, "pending")):
        refused = client.post(
            f"{API}/owner/churches/{hope.church.id}/close", headers=headers_of(client, who)
        )
        assert refused.status_code == 403
    admin_password = secrets.token_urlsafe(16)
    hope.admin.password_hash = hash_password(admin_password)
    session.flush()
    by_admin = client.post(
        f"{API}/owner/churches/{hope.church.id}/close",
        headers=headers_of(client, Member(hope.admin, admin_password)),
    )
    assert by_admin.status_code == 403  # not even the church's own ADMIN
    assert client.post(f"{API}/owner/churches/{hope.church.id}/close").status_code == 401
    assert session.get(Church, hope.church.id).closed_at is None  # type: ignore[union-attr]
    assert close(client, world, hope.church).status_code == 200
    assert close(client, world, hope.church).status_code == 404  # closed once


def test_closing_a_church_does_not_cost_a_query_per_member(
    client: TestClient, session: Session, world: World
) -> None:
    def statements_for(members: int, name: str) -> int:
        hope = Hope(world, members=members)
        hope.church.name = name
        session.flush()
        count = 0

        def record(*args: Any) -> None:
            nonlocal count
            count += 1

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", record)
        try:
            assert close(client, world, hope.church).status_code == 200
        finally:
            event.remove(bind, "before_cursor_execute", record)
        return count

    small = statements_for(2, "Small Church")
    large = statements_for(14, "Large Church")
    assert large - small <= 4, (small, large)


# --- the OWNER's list of churches ---------------------------------------------------------------


def test_the_owner_lists_the_churches_with_counts(
    client: TestClient, session: Session, world: World
) -> None:
    hope = Hope(world)
    owner = owner_member(world)
    listed = client.get(f"{API}/owner/churches", headers=headers_of(client, owner)).json()
    assert listed["total"] == 2
    by_name = {c["name"]: c for c in listed["items"]}
    assert by_name["Hope Church"]["groups"] == 2 and by_name["Hope Church"]["revoked"] == 1
    assert by_name["Hope Church"]["members"] == len(hope.everyone_open())
    assert by_name["Hope Church"]["open"] is True
    assert by_name["Hope Church"]["admin_name"] == hope.admin.full_name
    assert by_name["First church"]["admin_name"] == world.owner.full_name
    closed_now = client.post(
        f"{API}/owner/churches/{hope.church.id}/close", headers=headers_of(client, owner)
    )
    assert closed_now.status_code == 200
    after = client.get(f"{API}/owner/churches", headers=headers_of(client, owner)).json()
    assert [c["name"] for c in after["items"]] == ["First church", "Hope Church"]  # open first
    closed = after["items"][1]
    assert closed["open"] is False and closed["closed_at"] is not None
    assert (closed["groups"], closed["members"], closed["revoked"]) == (0, 0, 1)
    page = client.get(
        f"{API}/owner/churches", headers=headers_of(client, owner), params={"limit": 1}
    )
    assert len(page.json()["items"]) == 1 and page.json()["total"] == 2
    assert (
        client.get(
            f"{API}/owner/churches", headers=headers_of(client, owner), params={"limit": 101}
        ).status_code
        == 422
    )
    for who in (add_member(world, "provider"),):
        assert (
            client.get(f"{API}/owner/churches", headers=headers_of(client, who)).status_code == 403
        )
    assert client.get(f"{API}/owner/churches").status_code == 401
