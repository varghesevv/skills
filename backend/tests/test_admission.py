"""Admitting and declining applicants, and what the verifier screens list."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    ContactView,
    HomeGroup,
    Notification,
    Person,
    StatusChange,
    Vouch,
    VouchLink,
)
from tests.api_helpers import API
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World, check_rules

pytestmark = pytest.mark.db

V = f"{API}/verifier"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def headers_of(client: TestClient, member: Member) -> dict[str, str]:
    return bearer(login(client, member))


def group_of(session: Session, member: Member) -> HomeGroup:
    group = session.get(HomeGroup, member.person.home_group_id)
    assert group is not None
    return group


def leader(world: World) -> tuple[Member, HomeGroup]:
    """A VERIFIER who leads a group of their own, with that group."""
    member = add_member(world, "verifier")
    return member, group_of(world.session, member)


def owner_member(world: World) -> Member:
    member = Member(world.owner, secrets.token_urlsafe(16))
    world.owner.password_hash = hash_password(member.password)
    world.session.flush()
    return member


def add_vouch(world: World, applicant: Member, voucher: Member, **extra: Any) -> None:
    world.session.add(
        Vouch(applicant_id=applicant.person.id, voucher_id=voucher.person.id, **extra)
    )
    world.session.flush()


def get(client: TestClient, who: Member, path: str, **params: Any) -> Any:
    return client.get(f"{V}{path}", headers=headers_of(client, who), params=params)


def post(client: TestClient, who: Member, path: str, **body: Any) -> Any:
    return client.post(f"{V}{path}", headers=headers_of(client, who), json=body or None)


# --- who may use the screens ----------------------------------------------------------------


@pytest.mark.parametrize("status", ["pending", "searcher", "provider"])
@pytest.mark.parametrize(
    "path",
    [
        "/applicants",
        "/members",
        "/revoked",
        "/flagged",
        f"/people/{'0' * 8}-0000-0000-0000-{'0' * 12}",
    ],
)
def test_only_leaders_use_the_screens(
    client: TestClient, world: World, status: str, path: str
) -> None:
    response = get(client, add_member(world, status), path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_admitted"


# --- lists ----------------------------------------------------------------------------------


def test_applicants_are_in_scope_most_vouched_first_and_have_no_numbers(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    quiet = add_member(world, "pending", group=group, requested_status="searcher")
    popular = add_member(world, "pending", group=group, requested_status="provider")
    elsewhere = add_member(world, "pending", requested_status="searcher")  # first group
    gone = add_member(world, "pending", group=group)
    world.session.execute(  # a declined or left application is closed
        Person.__table__.update()
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
    admitted = add_member(world, "searcher", group=group)
    for voucher in (add_member(world, "searcher"), add_member(world, "provider")):
        add_vouch(world, popular, voucher)
    add_vouch(world, popular, add_member(world, "searcher"), withdrawn_at=datetime.now(UTC))
    body = get(client, lead, "/applicants").json()
    assert [row["id"] for row in body["items"]] == [str(popular.person.id), str(quiet.person.id)]
    assert body["total"] == 2
    first = body["items"][0]
    assert first["vouch_count"] == 2 and len(first["vouchers"]) == 3
    assert sorted(v["live"] for v in first["vouchers"]) == [False, True, True]
    assert first["requested_status"] == "provider" and first["home_group"]["id"] == str(group.id)
    text = str(body)
    for person in (quiet, popular, elsewhere, admitted):
        assert person.person.mobile_number not in text and person.person.email not in text
    assert str(elsewhere.person.id) not in text and str(admitted.person.id) not in text


def test_a_revoked_vouch_does_not_count(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group)
    voucher = add_member(world, "searcher")
    add_vouch(world, applicant, voucher)
    world.session.execute(
        Person.__table__.update()
        .where(Person.id == voucher.person.id)
        .values(status="revoked", home_group_id=None, last_home_group_id=world.group.id)
    )
    row = get(client, lead, "/applicants").json()["items"][0]
    assert row["vouch_count"] == 0 and [v["live"] for v in row["vouchers"]] == [False]


def test_an_admin_sees_the_church_and_the_owner_everyone(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    in_group = add_member(world, "pending", group=group)
    in_first = add_member(world, "pending")
    church, other_group, admin = world.add_church()
    abroad = add_member(world, "pending")  # added to the first church; move it
    world.session.execute(
        Person.__table__.update()
        .where(Person.id == abroad.person.id)
        .values(church_id=church.id, home_group_id=other_group.id)
    )
    admin_member = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(admin_member.password)
    world.session.flush()
    ids = lambda who: {r["id"] for r in get(client, who, "/applicants").json()["items"]}  # noqa: E731
    assert ids(admin_member) == {str(abroad.person.id)}
    assert ids(owner_member(world)) == {
        str(in_group.person.id),
        str(in_first.person.id),
        str(abroad.person.id),
    }
    assert ids(lead) == {str(in_group.person.id)}


def test_members_filter_and_scope(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    s = add_member(world, "searcher", group=group, full_name="Bea")
    p = add_member(world, "provider", group=group, full_name="Abe")
    lead.person.full_name = "Cal"
    add_member(world, "pending", group=group)
    add_member(world, "searcher")  # other group
    world.session.flush()

    def names(**query: Any) -> list[str]:
        return [r["full_name"] for r in get(client, lead, "/members", **query).json()["items"]]

    assert names() == ["Abe", "Bea", "Cal"]  # admitted people of the group, by name
    assert names(status="provider") == ["Abe"]
    assert names(home_group_id=str(group.id)) == ["Abe", "Bea", "Cal"]
    assert names(home_group_id=str(world.group.id)) == []
    assert get(client, lead, "/members", status="pending").status_code == 422
    text = get(client, lead, "/members").text
    assert s.person.mobile_number not in text and p.person.mobile_number not in text


def test_lists_are_paged(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    for _ in range(3):
        add_member(world, "pending", group=group)
    page = get(client, lead, "/applicants", limit=2, offset=1).json()
    assert len(page["items"]) == 2 and page["total"] == 3
    assert get(client, lead, "/applicants", limit=101).status_code == 422
    assert get(client, lead, "/applicants", offset=-1).status_code == 422


def test_revoked_and_flagged_lists(client: TestClient, session: Session, world: World) -> None:
    lead, group = leader(world)
    out = add_member(world, "revoked", last_home_group_id=group.id)
    session.add(
        StatusChange(
            person_id=out.person.id,
            from_status="searcher",
            to_status="revoked",
            changed_by_id=lead.person.id,
            kind="revoke",
        )
    )
    flagged = add_member(world, "provider", group=group, flagged_for_recheck=True)
    add_member(world, "revoked", last_home_group_id=world.group.id)  # first group: not ours
    session.flush()
    revoked = get(client, lead, "/revoked").json()
    assert [r["id"] for r in revoked["items"]] == [str(out.person.id)]
    assert revoked["items"][0]["revoked_by"] == {"name": lead.person.full_name}
    assert revoked["items"][0]["removed_from"]["id"] == str(group.id)
    assert revoked["items"][0]["revoked_at"] is not None
    flags = get(client, lead, "/flagged").json()
    assert [r["id"] for r in flags["items"]] == [str(flagged.person.id)]
    assert "mobile" not in str(revoked) + str(flags)


# --- one person -------------------------------------------------------------------------------


def test_one_person_shows_the_number_history_and_chain_and_is_logged(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "provider", group=group, status_set_by_id=lead.person.id)
    session.add(
        StatusChange(
            person_id=member.person.id,
            from_status="pending",
            to_status="provider",
            changed_by_id=lead.person.id,
            kind="admit",
        )
    )
    lead.person.status_set_by_id = world.owner.id
    session.flush()
    response = get(client, lead, f"/people/{member.person.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["mobile_number"] == member.person.mobile_number
    assert body["history"][0]["kind"] == "admit"
    assert body["history"][0]["changed_by"] == {"name": lead.person.full_name}
    assert [c["status"] for c in body["chain_of_trust"]] == ["verifier", "owner"]
    views = session.scalars(select(ContactView)).all()
    assert [(v.viewer_id, v.person_id, v.screen) for v in views] == [
        (lead.person.id, member.person.id, "person")
    ]
    get(client, lead, f"/people/{member.person.id}")
    assert session.scalar(select(func.count()).select_from(ContactView)) == 2
    assert not hasattr(views[0], "mobile_number")


def test_out_of_scope_closed_or_unknown_is_404_and_not_logged(
    client: TestClient, session: Session, world: World
) -> None:
    lead, _ = leader(world)
    other = add_member(world, "searcher")  # first group
    closed = add_member(world, "searcher")
    for target in (other.person.id, "00000000-0000-4000-8000-000000000000"):
        response = get(client, lead, f"/people/{target}")
        assert response.status_code == 404
    assert session.scalar(select(func.count()).select_from(ContactView)) == 0
    # The same answer for someone who exists and someone who does not.
    one = get(client, lead, f"/people/{other.person.id}").text
    two = get(client, lead, "/people/00000000-0000-4000-8000-000000000000").text
    assert one == two
    del closed


def test_a_revoked_person_is_in_the_scope_of_their_old_group(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    out = add_member(world, "revoked", last_home_group_id=group.id)
    body = get(client, lead, f"/people/{out.person.id}").json()
    assert body["home_group"]["id"] == str(group.id)


# --- admit ------------------------------------------------------------------------------------


def admit(client: TestClient, who: Member, target: Member, to: str) -> Any:
    return client.post(
        f"{V}/people/{target.person.id}/admit", headers=headers_of(client, who), json={"to": to}
    )


def test_admit_a_searcher_changes_everything_together(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group, requested_status="searcher")
    link = VouchLink(
        person_id=applicant.person.id,
        token_hash=secrets.token_hex(16),
        expires_at=datetime(2100, 1, 1, tzinfo=UTC),
    )
    session.add(link)
    session.flush()
    response = admit(client, lead, applicant, "searcher")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(applicant.person.id),
        "status": "searcher",
        "requested_status": None,
    }
    session.refresh(applicant.person)
    assert applicant.person.status == "searcher"
    assert applicant.person.status_set_by_id == lead.person.id
    change = session.scalars(
        select(StatusChange).where(StatusChange.person_id == applicant.person.id)
    ).one()
    assert (change.kind, change.from_status, change.to_status, change.changed_by_id) == (
        "admit",
        "pending",
        "searcher",
        lead.person.id,
    )
    note = session.scalars(
        select(Notification).where(Notification.person_id == applicant.person.id)
    ).one()
    assert (note.kind, note.subject_id) == ("admitted", lead.person.id)
    session.refresh(link)
    assert link.revoked_at is not None
    check_rules(session)
    me = client.get(f"{API}/me", headers=headers_of(client, applicant)).json()
    assert me["status"] == "searcher" and me["status_set_by"] == {"name": lead.person.full_name}


def test_a_provider_needs_a_vouch_from_someone_besides_the_leader(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group, requested_status="provider")
    refused = admit(client, lead, applicant, "provider")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "not_enough_vouches"
    add_vouch(world, applicant, lead)  # the leader's own vouch is their sign-off, not a second one
    assert admit(client, lead, applicant, "provider").status_code == 409
    voucher = add_member(world, "searcher")
    add_vouch(world, applicant, voucher, withdrawn_at=datetime.now(UTC))
    assert admit(client, lead, applicant, "provider").status_code == 409  # withdrawn
    session.execute(Vouch.__table__.update().values(withdrawn_at=None))
    assert admit(client, lead, applicant, "provider").status_code == 200
    session.refresh(applicant.person)
    assert applicant.person.status == "provider" and applicant.person.requested_status is None
    check_rules(session)


def test_the_admin_and_the_owner_admit_in_any_group_of_their_scope(
    client: TestClient, world: World
) -> None:
    _, group = leader(world)
    for_owner = add_member(world, "pending", group=group)
    assert admit(client, owner_member(world), for_owner, "searcher").status_code == 200
    church, other_group, admin = world.add_church()
    admin_member = Member(admin, secrets.token_urlsafe(16))
    admin.password_hash = hash_password(admin_member.password)
    world.session.flush()
    other = add_member(world, "pending", group=group)  # not the admin's church
    assert admit(client, admin_member, other, "searcher").status_code == 404
    del church, other_group


def test_a_leader_cannot_admit_outside_their_group_or_themselves(
    client: TestClient, world: World
) -> None:
    lead, _ = leader(world)
    elsewhere = add_member(world, "pending")
    response = admit(client, lead, elsewhere, "searcher")
    assert response.status_code == 404
    assert response.text == admit(client, lead, lead, "searcher").text
    assert (
        client.post(
            f"{V}/people/00000000-0000-4000-8000-000000000000/admit",
            headers=headers_of(client, lead),
            json={"to": "searcher"},
        ).text
        == response.text
    )


def test_only_applicants_are_admitted(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group)  # not applying to provide
    for to in ("searcher", "provider"):
        response = admit(client, lead, member, to)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "not_pending"
    assert (
        client.post(
            f"{V}/people/{member.person.id}/admit",
            headers=headers_of(client, lead),
            json={"to": "owner"},
        ).status_code
        == 422
    )


def test_a_searcher_who_applies_to_provide_is_admitted_with_vouches(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group, requested_status="provider")
    assert admit(client, lead, member, "searcher").status_code == 409  # already one
    add_vouch(world, member, add_member(world, "provider"))
    assert admit(client, lead, member, "provider").status_code == 200
    session.refresh(member.person)
    assert (member.person.status, member.person.requested_status) == ("provider", None)
    check_rules(session)


def test_admitted_as_a_searcher_while_applying_to_provide_keeps_collecting(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group, requested_status="provider")
    response = admit(client, lead, applicant, "searcher")
    assert response.json()["status"] == "searcher"
    assert response.json()["requested_status"] == "provider"


def test_admitting_twice_is_refused(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group)
    assert admit(client, lead, applicant, "searcher").status_code == 200
    assert admit(client, lead, applicant, "searcher").status_code == 409


# --- decline ----------------------------------------------------------------------------------


def decline(client: TestClient, who: Member, target: Member) -> Any:
    return client.post(f"{V}/people/{target.person.id}/decline", headers=headers_of(client, who))


def test_declining_closes_the_application_and_revokes_nobody(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group)
    email, password = applicant.person.email, applicant.password
    voucher = add_member(world, "searcher")
    add_vouch(world, applicant, voucher)
    tokens = login(client, applicant)
    assert decline(client, lead, applicant).status_code == 204
    session.refresh(applicant.person)
    person = applicant.person
    assert person.closed_at is not None and person.status == "pending"
    assert person.email is None and person.full_name is None and person.mobile_number is None
    assert session.scalar(select(func.count()).select_from(Vouch)) == 1  # the history stays
    assert (
        client.get(f"{API}/me", headers=bearer(tokens)).status_code == 401
    )  # and the session is over
    again = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert again.status_code == 401
    assert get(client, lead, f"/people/{person.id}").status_code == 404
    assert get(client, lead, "/applicants").json()["items"] == []
    assert get(client, lead, "/revoked").json()["items"] == []
    check_rules(session)


def test_a_declined_person_can_sign_up_again(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    applicant = add_member(world, "pending", group=group)
    email = applicant.person.email
    decline(client, lead, applicant)
    response = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Back Again",
            "email": email,
            "mobile_number": "+971500099999",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(group.id),
        },
    )
    assert response.status_code == 201, response.text


def test_decline_checks_scope_and_state(client: TestClient, world: World) -> None:
    lead, group = leader(world)
    elsewhere = add_member(world, "pending")
    assert decline(client, lead, elsewhere).status_code == 404
    member = add_member(world, "searcher", group=group)
    refused = decline(client, lead, member)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_pending"
    assert decline(client, lead, lead).status_code == 404
    searcher = add_member(world, "provider")
    assert (
        client.post(
            f"{V}/people/{elsewhere.person.id}/decline", headers=headers_of(client, searcher)
        ).status_code
        == 403
    )
