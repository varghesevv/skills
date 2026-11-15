"""A searcher who wants to become a provider: apply, collect vouches, be admitted or declined."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HomeGroup, Notification, Person, StatusChange, Vouch, VouchLink
from app.services import notifications, rate_limit
from tests.api_helpers import API
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    rate_limit.link_lookup_limiter.reset()
    rate_limit.vouch_attempt_limiter.reset()


def headers_of(client: TestClient, member: Member) -> dict[str, str]:
    return bearer(login(client, member))


def leader(world: World) -> tuple[Member, HomeGroup]:
    member = add_member(world, "verifier")
    group = world.session.get(HomeGroup, member.person.home_group_id)
    assert group is not None
    return member, group


def apply(client: TestClient, member: Member) -> Any:
    return client.post(f"{API}/me/apply-provider", headers=headers_of(client, member))


def notes(session: Session, to: Member) -> list[Notification]:
    return list(session.scalars(select(Notification).where(Notification.person_id == to.person.id)))


def test_a_searcher_applies_keeps_their_status_and_the_leader_is_told(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    searcher = add_member(world, "searcher", group=group)
    response = apply(client, searcher)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "searcher" and body["requested_status"] == "provider"
    session.refresh(searcher.person)
    assert searcher.person.requested_status == "provider"
    told = [n for n in notes(session, lead) if n.kind == "provider_application"]
    assert [n.subject_id for n in told] == [searcher.person.id]
    assert "provider_application" in notifications.KINDS
    check_rules(session)


def test_applying_again_changes_nothing_and_tells_nobody_twice(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    searcher = add_member(world, "searcher", group=group)
    assert apply(client, searcher).status_code == 200
    assert apply(client, searcher).status_code == 200
    assert len([n for n in notes(session, lead) if n.kind == "provider_application"]) == 1


@pytest.mark.parametrize("status", ["provider", "verifier"])
def test_only_a_searcher_can_apply(client: TestClient, world: World, status: str) -> None:
    response = apply(client, add_member(world, status))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_searcher"


def test_an_applicant_and_a_revoked_person_cannot(client: TestClient, world: World) -> None:
    pending = apply(client, add_member(world, "pending"))
    assert pending.status_code == 403 and pending.json()["error"]["code"] == "not_admitted"
    revoked = add_member(world, "revoked", last_home_group_id=world.group.id)
    response = apply(client, revoked)
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_revoked"
    assert client.post(f"{API}/me/apply-provider").status_code == 401


def test_the_whole_way_from_applying_to_being_admitted(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    searcher = add_member(world, "searcher", group=group)
    voucher = add_member(world, "provider")
    apply(client, searcher)
    link = client.post(f"{API}/me/vouch-link", headers=headers_of(client, searcher))
    assert link.status_code == 201
    token = link.json()["token"]
    assert (
        client.post(
            f"{API}/vouch-links/vouch", headers=headers_of(client, voucher), json={"token": token}
        ).status_code
        == 201
    )
    # They keep searching while they collect vouches.
    assert (
        client.get(f"{API}/me/vouches-given", headers=headers_of(client, searcher)).status_code
        == 200
    )

    listed = client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()
    row = next(r for r in listed["items"] if r["id"] == str(searcher.person.id))
    assert row["status"] == "searcher" and row["requested_status"] == "provider"
    assert row["vouch_count"] == 1 and row["can_admit_as_provider"] is True

    admitted = client.post(
        f"{API}/verifier/people/{searcher.person.id}/admit",
        headers=headers_of(client, lead),
        json={"to": "provider"},
    )
    assert admitted.status_code == 200
    assert admitted.json() == {
        "id": str(searcher.person.id),
        "status": "provider",
        "requested_status": None,
    }
    change = session.scalars(
        select(StatusChange).where(StatusChange.person_id == searcher.person.id)
    ).one()
    assert (change.kind, change.from_status, change.to_status) == ("admit", "searcher", "provider")
    assert (
        session.scalars(select(VouchLink).where(VouchLink.person_id == searcher.person.id))
        .one()
        .revoked_at
    )
    after = client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()
    assert str(searcher.person.id) not in str(after)
    check_rules(session)


def test_the_leaders_own_sign_off_is_not_enough_for_a_provider(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    searcher = add_member(world, "searcher", group=group, requested_status="provider")
    world.session.add(Vouch(applicant_id=searcher.person.id, voucher_id=lead.person.id))
    world.session.flush()
    row = client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()[
        "items"
    ][0]
    assert row["can_admit_as_provider"] is False
    refused = client.post(
        f"{API}/verifier/people/{searcher.person.id}/admit",
        headers=headers_of(client, lead),
        json={"to": "provider"},
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_enough_vouches"


def test_the_list_holds_applicants_and_upgrade_requests_only(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    pending = add_member(world, "pending", group=group)
    asking = add_member(world, "searcher", group=group, requested_status="provider")
    add_member(world, "searcher", group=group)  # a plain searcher
    add_member(world, "provider", group=group)
    elsewhere = add_member(world, "searcher", requested_status="provider")  # first group
    items = client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()[
        "items"
    ]
    assert {r["id"] for r in items} == {str(pending.person.id), str(asking.person.id)}
    assert {r["status"] for r in items} == {"pending", "searcher"}
    assert str(elsewhere.person.id) not in str(items)


def test_a_closed_searcher_is_not_listed(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    gone = add_member(world, "searcher", group=group, requested_status="provider")
    from sqlalchemy import update

    session.execute(
        update(Person)
        .where(Person.id == gone.person.id)
        .values(
            closed_at=datetime.now(UTC),
            home_group_id=None,
            full_name=None,
            email=None,
            mobile_number=None,
            password_hash=None,
        )
    )
    items = client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()[
        "items"
    ]
    assert items == []


def decline(client: TestClient, who: Member, target: Member) -> Any:
    return client.post(
        f"{API}/verifier/people/{target.person.id}/decline", headers=headers_of(client, who)
    )


def test_declining_a_request_ends_it_and_leaves_a_searcher(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    searcher = add_member(world, "searcher", group=group)
    voucher = add_member(world, "provider")
    apply(client, searcher)
    token = client.post(f"{API}/me/vouch-link", headers=headers_of(client, searcher)).json()[
        "token"
    ]
    client.post(
        f"{API}/vouch-links/vouch", headers=headers_of(client, voucher), json={"token": token}
    )
    assert decline(client, lead, searcher).status_code == 204
    session.refresh(searcher.person)
    person = searcher.person
    assert (person.status, person.requested_status, person.closed_at) == ("searcher", None, None)
    assert person.email is not None  # the account is not closed
    assert client.get(f"{API}/me", headers=headers_of(client, searcher)).status_code == 200
    # The link stops working; the vouch stays on record.
    assert (
        client.post(
            f"{API}/vouch-links/lookup", headers=headers_of(client, voucher), json={"token": token}
        ).status_code
        == 404
    )
    assert session.scalars(select(Vouch).where(Vouch.applicant_id == person.id)).one()
    told = [n for n in notes(session, searcher) if n.kind == "provider_declined"]
    assert [n.subject_id for n in told] == [lead.person.id]
    assert "provider_declined" in notifications.KINDS
    assert (
        client.get(f"{API}/verifier/applicants", headers=headers_of(client, lead)).json()["items"]
        == []
    )
    # It can be asked again, and the old request cannot be admitted any more.
    assert (
        client.post(
            f"{API}/verifier/people/{person.id}/admit",
            headers=headers_of(client, lead),
            json={"to": "provider"},
        ).status_code
        == 409
    )
    assert apply(client, searcher).status_code == 200
    check_rules(session)


def test_a_leader_cannot_decline_outside_their_group(client: TestClient, world: World) -> None:
    lead, _ = leader(world)
    elsewhere = add_member(world, "searcher", requested_status="provider")
    assert decline(client, lead, elsewhere).status_code == 404


def test_a_plain_searcher_cannot_be_declined(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    plain = add_member(world, "searcher", group=group)
    refused = decline(client, lead, plain)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_pending"
