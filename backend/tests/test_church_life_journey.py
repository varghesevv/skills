"""The church life of slice S4, through the real endpoints and a real database.

Three stories that cross several pieces of the model, each ending with the rules checked by the
database: a leader who cannot leave until their group is handed on, a revocation of a leader that
flags the people they set and a successor who re-confirms them, and a planned handover of the
OWNER role. The web and the mobile app make exactly these calls.
"""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Church, HomeGroup, Notification, Person, StatusChange
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db

V = f"{API}/verifier"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def refresh(session: Session, *people: Member | Person) -> None:
    for who in people:
        session.refresh(who.person if isinstance(who, Member) else who)


def leave(client: TestClient, who: Member, password: str | None = None) -> Any:
    return client.request(
        "DELETE",
        f"{API}/me",
        headers=headers_of(client, who),
        json={"password": password or who.password},
    )


def login_status(client: TestClient, who: Member) -> int:
    response = client.post(f"{API}/auth/login", json={"email": who.email, "password": who.password})
    status: int = response.status_code
    return status


def kinds(session: Session, who: Member) -> list[str]:
    rows = session.scalars(select(Notification).where(Notification.person_id == who.person.id))
    return sorted(n.kind for n in rows)


def test_a_leader_leaves_only_after_handing_the_group_on(
    client: TestClient, session: Session, world: World
) -> None:
    # Hal leads a group of his own and is its only member, in a church of other groups.
    hal, hal_group = leader(world)
    other_lead, other_group = leader(world)

    # 1. A leader cannot just close their account: the answer says why, and nothing changes.
    refused = leave(client, hal)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "leads_a_group"
    assert login_status(client, hal) == 200

    # 2. A wrong password is refused before anything else is looked at.
    wrong = leave(client, hal, secrets.token_urlsafe(16))
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "invalid_password"

    # 3. Hal closes the group he leads by joining another one, and becomes a provider.
    closed = client.post(
        f"{API}/home-groups/{hal_group.id}/close",
        headers=headers_of(client, hal),
        json={"move_to_group_id": str(other_group.id), "former_leader_status": "provider"},
    )
    assert closed.status_code == 200, closed.text
    refresh(session, hal)
    assert hal.person.status == "provider" and hal.person.home_group_id == other_group.id
    assert session.get(HomeGroup, hal_group.id).closed_at is not None  # type: ignore[union-attr]

    # 4. Now he may leave: the account closes, the row and its history stay, nobody is revoked.
    assert leave(client, hal).status_code == 204
    assert login_status(client, hal) == 401
    refresh(session, hal)
    assert hal.person.closed_at is not None
    assert (
        session.scalar(select(func.count()).select_from(Person).where(Person.status == "revoked"))
        == 0
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(StatusChange)
            .where(StatusChange.person_id == hal.person.id)
        )
        or 0
    ) >= 1
    assert other_lead.person.status == "verifier"
    check_rules(session)


def test_a_revoked_leader_flags_who_they_set_and_the_successor_reconfirms(
    client: TestClient, session: Session, world: World
) -> None:
    owner = owner_member(world)
    lena, group = leader(world)
    mia = add_member(world, "provider", group=group, status_set_by_id=lena.person.id)
    max_ = add_member(world, "searcher", group=group, status_set_by_id=lena.person.id)
    nobody_of_lena = add_member(
        world, "provider", group=world.group, status_set_by_id=owner.person.id
    )

    # 1. The OWNER cannot revoke a leader without saying who leads the group next.
    alone = client.put(
        f"{V}/people/{lena.person.id}/status",
        headers=headers_of(client, owner),
        json={"to": "revoked"},
    )
    assert alone.status_code == 409
    assert alone.json()["error"]["code"] == "successor_required"
    refresh(session, lena)
    assert lena.person.status == "verifier"

    # 2. With Mia as successor: Lena is revoked, Mia leads, and everyone Lena set is flagged.
    revoked = client.put(
        f"{V}/people/{lena.person.id}/status",
        headers=headers_of(client, owner),
        json={"to": "revoked", "successor_id": str(mia.person.id)},
    )
    assert revoked.status_code == 200, revoked.text
    refresh(session, lena, mia, max_, nobody_of_lena)
    session.refresh(group)
    assert lena.person.status == "revoked" and lena.person.home_group_id is None
    assert mia.person.status == "verifier" and group.leader_id == mia.person.id
    assert max_.person.flagged_for_recheck is True and max_.person.status == "searcher"
    assert nobody_of_lena.person.flagged_for_recheck is False
    check_rules(session)

    # 3. The revoked leader keeps a login but has no way in, and cannot leave on their own.
    assert login_status(client, lena) == 200
    assert client.get(f"{V}/members", headers=headers_of(client, lena)).status_code == 403
    gone = leave(client, lena)
    assert gone.status_code == 403 and gone.json()["error"]["code"] == "account_revoked"

    # 4. The new leader sees who needs a re-check, and Max, who keeps his access, is on the list.
    listed = client.get(f"{V}/flagged", headers=headers_of(client, mia)).json()["items"]
    assert str(max_.person.id) in {row["id"] for row in listed}
    assert (
        client.get(f"{API}/me/notifications", headers=headers_of(client, max_)).status_code == 200
    )

    # 5. Mia re-confirms Max: the flag goes, she becomes his new link, and the history says so.
    again = client.post(f"{V}/people/{max_.person.id}/reconfirm", headers=headers_of(client, mia))
    assert again.status_code == 200 and again.json()["flagged_for_recheck"] is False
    refresh(session, max_)
    assert (
        max_.person.status_set_by_id == mia.person.id and max_.person.flagged_for_recheck is False
    )
    last = session.scalars(
        select(StatusChange)
        .where(StatusChange.person_id == max_.person.id)
        .order_by(StatusChange.at)
    ).all()[-1]
    assert (last.kind, last.changed_by_id) == ("reconfirm", mia.person.id)
    listed = client.get(f"{V}/flagged", headers=headers_of(client, mia)).json()["items"]
    assert str(max_.person.id) not in {row["id"] for row in listed}

    # 6. Lena may be brought back by the OWNER into a group of the church, as a provider.
    back = client.put(
        f"{V}/people/{lena.person.id}/status",
        headers=headers_of(client, owner),
        json={"to": "provider", "home_group_id": str(group.id)},
    )
    assert back.status_code == 200, back.text
    refresh(session, lena)
    assert lena.person.status == "provider" and lena.person.home_group_id == group.id
    check_rules(session)


def test_the_owner_hands_the_role_on_in_one_step(
    client: TestClient, session: Session, world: World
) -> None:
    owner = owner_member(world)
    in_group = add_member(world, "provider")  # a member of the OWNER's own group
    church_two, group_two, admin_two = world.add_church("Hope Church")
    ada = Member(admin_two, secrets.token_urlsafe(16))
    admin_two.password_hash = hash_password(ada.password)
    session.flush()
    elsewhere = add_member(world, "searcher", group=world.group)
    check_rules(session)

    # 1. Only the OWNER proposes, and only to the ADMIN of another church.
    stranger = add_member(world, "provider")
    refused = client.post(
        f"{API}/owner/handover",
        headers=headers_of(client, stranger),
        json={"new_owner_id": str(ada.person.id)},
    )
    assert refused.status_code == 403
    not_an_admin = client.post(
        f"{API}/owner/handover",
        headers=headers_of(client, owner),
        json={"new_owner_id": str(in_group.person.id)},
    )
    assert not_an_admin.status_code == 422
    assert not_an_admin.json()["error"]["code"] == "invalid_choice"

    # 2. The OWNER proposes; nothing moves yet, and the chosen ADMIN sees the proposal.
    proposed = client.post(
        f"{API}/owner/handover",
        headers=headers_of(client, owner),
        json={
            "new_owner_id": str(ada.person.id),
            "successor_admin_id": str(elsewhere.person.id),
            "successor_leader_id": str(in_group.person.id),
            "former_owner_status": "provider",
        },
    )
    assert proposed.status_code == 201, proposed.text
    refresh(session, world.owner)
    assert world.owner.status == "owner"
    seen = client.get(f"{API}/owner/handover", headers=headers_of(client, ada))
    assert seen.status_code == 200 and seen.json() is not None
    assert kinds(session, ada) == ["handover_requested"]

    # 3. The ADMIN accepts: every role moves together, and there is still exactly one OWNER.
    accepted = client.post(
        f"{API}/owner/handover/{proposed.json()['id']}/accept", headers=headers_of(client, ada)
    )
    assert accepted.status_code == 200, accepted.text
    refresh(session, world.owner, admin_two, elsewhere, in_group)
    session.refresh(world.church)
    session.refresh(world.group)
    assert admin_two.status == "owner" and world.owner.status == "provider"
    assert world.church.admin_id == elsewhere.person.id and elsewhere.person.status == "admin"
    assert world.group.leader_id == in_group.person.id and in_group.person.status == "verifier"
    assert (
        session.scalar(
            select(func.count())
            .select_from(Person)
            .where(Person.status == "owner", Person.closed_at.is_(None))
        )
        == 1
    )
    assert session.get(Church, church_two.id).admin_id == admin_two.id  # type: ignore[union-attr]
    assert session.get(HomeGroup, group_two.id) is not None

    # 4. The new OWNER has the OWNER's reach, and the old one no longer has.
    assert client.get(f"{API}/owner/churches", headers=headers_of(client, ada)).status_code == 200
    assert client.get(f"{API}/owner/churches", headers=headers_of(client, owner)).status_code == 403
    check_rules(session)
