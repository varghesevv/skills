"""The provider's own profile, labels and unavailability, and who manages labels (slice S5.1).

These belong to the person (decision D-41): a PROVIDER or above edits them; a SEARCHER or an
applicant has no profile to edit; the OWNER manages the labels.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import PersonLabel
from app.models.labels import Label
from tests.api_helpers import API, label_id, older_actor
from tests.test_admission import headers_of, owner_member
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def period(start_days: int, end_days: int) -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "unavailable_from": (now + timedelta(days=start_days)).isoformat(),
        "unavailable_to": (now + timedelta(days=end_days)).isoformat(),
    }


def put_profile(client: TestClient, who: Member, **fields: Any) -> Any:
    body = {"mobile_number": "+971501234567", **fields}
    return client.put(f"{API}/freelancers/me", json=body, headers=headers_of(client, who))


# ---- who has a profile --------------------------------------------------------------------


@pytest.mark.parametrize("status", ["provider", "verifier", "admin", "owner"])
def test_a_provider_or_above_has_a_profile(client: TestClient, world: World, status: str) -> None:
    member = add_member(world, status)
    response = client.get(f"{API}/freelancers/me", headers=headers_of(client, member))
    assert response.status_code == 200
    assert response.json()["id"] == str(member.person.id)
    assert response.json()["email"] == member.email


@pytest.mark.parametrize("status", ["pending", "searcher"])
def test_an_applicant_or_a_searcher_has_none(client: TestClient, world: World, status: str) -> None:
    member = add_member(world, status)
    headers = headers_of(client, member)
    for method, path in (
        ("GET", "/freelancers/me"),
        ("PUT", "/freelancers/me"),
        ("PUT", "/freelancers/me/labels"),
        ("GET", "/freelancers/me/unavailability"),
        ("POST", "/freelancers/me/unavailability"),
    ):
        response = client.request(method, f"{API}{path}", headers=headers, json={})
        assert (response.status_code, response.json()["error"]["code"]) == (
            403,
            "not_admitted",
        ), path


def test_a_revoked_person_has_none_and_the_door_is_closed_without_a_token(
    client: TestClient, world: World
) -> None:
    member = add_member(world, "provider")
    headers = headers_of(client, member)
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.get(f"{API}/freelancers/me", headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")
    assert client.get(f"{API}/freelancers/me").status_code == 401


def test_a_token_of_an_older_account_type_has_no_profile(client: TestClient, world: World) -> None:
    old = older_actor("freelancer")
    assert client.get(f"{API}/freelancers/me", headers=old.headers).status_code == 401


# ---- the profile --------------------------------------------------------------------------


def test_a_provider_updates_their_own_profile(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    response = put_profile(
        client,
        member,
        mobile_number="+971 50 123 4567",
        whatsapp_availability=True,
        nationality="Indian",
        primary_language="Hindi",
        rate_per_hour=45.5,
        rate_currency="AED",
        is_rate_negotiable=True,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mobile_number"] == "+971501234567" and body["rate_per_hour"] == 45.5
    world.session.refresh(member.person)
    person = member.person
    assert (person.nationality, person.rate_currency, person.whatsapp_availability) == (
        "Indian",
        "AED",
        True,
    )
    again = client.get(f"{API}/freelancers/me", headers=headers_of(client, member)).json()
    assert again["rate_currency"] == "AED" and again["is_rate_negotiable"] is True


def test_the_name_changes_only_when_given(client: TestClient, world: World) -> None:
    member = add_member(world, "provider", full_name="Old Name")
    assert put_profile(client, member, full_name="  New Name ").json()["full_name"] == "New Name"
    assert put_profile(client, member).json()["full_name"] == "New Name"  # left out: unchanged
    assert put_profile(client, member, full_name="A").status_code == 422


def test_a_mobile_number_that_belongs_to_someone_else_is_refused(
    client: TestClient, world: World
) -> None:
    first = add_member(world, "provider", mobile_number="+971500000111")
    second = add_member(world, "provider")
    response = put_profile(client, second, mobile_number=first.person.mobile_number)
    assert response.status_code == 409 and response.json()["error"]["code"] == "account_exists"


@pytest.mark.parametrize(
    "extra",
    [
        {"rate_per_hour": 10},  # no currency
        {"rate_currency": "AED"},  # no rate
        {"rate_per_hour": 10, "rate_currency": "aed"},  # not capitals
        {"rate_per_hour": -1, "rate_currency": "AED"},  # negative
    ],
)
def test_a_rate_needs_a_valid_currency(
    client: TestClient, world: World, extra: dict[str, Any]
) -> None:
    assert put_profile(client, add_member(world, "provider"), **extra).status_code == 422


# ---- labels -------------------------------------------------------------------------------


def test_labels_with_skill_levels_and_replacing_the_set(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    headers = headers_of(client, member)
    plumbing = label_id(world.session, "skill", "plumbing")
    basic = label_id(world.session, "skill_level", "basic")
    english = label_id(world.session, "language", "English")
    body = {"labels": [{"label_id": plumbing, "level_label_id": basic}, {"label_id": english}]}
    response = client.put(f"{API}/freelancers/me/labels", json=body, headers=headers)
    assert response.status_code == 200, response.text
    by_name = {item["label"]["label_name"]: item for item in response.json()}
    assert by_name["plumbing"]["level"]["label_name"] == "basic"
    assert by_name["English"]["level"] is None
    rows = world.session.scalars(
        select(PersonLabel).where(PersonLabel.person_id == member.person.id)
    ).all()
    assert len(rows) == 2

    only_english = {"labels": [{"label_id": english}]}
    again = client.put(f"{API}/freelancers/me/labels", json=only_english, headers=headers)
    assert [item["label"]["label_name"] for item in again.json()] == ["English"]
    assert len(client.get(f"{API}/freelancers/me", headers=headers).json()["labels"]) == 1


def test_labels_of_one_person_are_not_another_persons(client: TestClient, world: World) -> None:
    one, two = add_member(world, "provider"), add_member(world, "provider")
    english = label_id(world.session, "language", "English")
    client.put(
        f"{API}/freelancers/me/labels",
        json={"labels": [{"label_id": english}]},
        headers=headers_of(client, one),
    )
    assert (
        client.get(f"{API}/freelancers/me", headers=headers_of(client, two)).json()["labels"] == []
    )


@pytest.mark.parametrize(
    "name",
    [
        "level on a language",
        "level is not a level",
        "skill level on its own",
        "duplicate",
        "unknown",
    ],
)
def test_invalid_label_selections_are_refused(client: TestClient, world: World, name: str) -> None:
    member = add_member(world, "provider")
    plumbing = label_id(world.session, "skill", "plumbing")
    basic = label_id(world.session, "skill_level", "basic")
    english = label_id(world.session, "language", "English")
    bodies = {
        "level on a language": [{"label_id": english, "level_label_id": basic}],
        "level is not a level": [{"label_id": plumbing, "level_label_id": english}],
        "skill level on its own": [{"label_id": basic}],
        "duplicate": [{"label_id": english}, {"label_id": english}],
        "unknown": [{"label_id": "00000000-0000-4000-8000-000000000000"}],
    }
    response = client.put(
        f"{API}/freelancers/me/labels",
        json={"labels": bodies[name]},
        headers=headers_of(client, member),
    )
    assert response.status_code == 422


def test_the_owner_manages_labels_and_nobody_else_does(client: TestClient, world: World) -> None:
    owner = owner_member(world)
    others = {
        status: add_member(world, status)
        for status in ("searcher", "provider", "verifier", "admin")
    }
    body = {"label_name": "carpentry", "label_type": "skill"}
    for status, who in others.items():
        refused = client.post(f"{API}/labels", json=body, headers=headers_of(client, who))
        assert refused.status_code == 403, status
    created = client.post(f"{API}/labels", json=body, headers=headers_of(client, owner))
    assert created.status_code == 201, created.text
    assert (
        client.post(f"{API}/labels", json=body, headers=headers_of(client, owner)).status_code
        == 409
    )
    url = f"{API}/labels/{created.json()['id']}"
    for who in others.values():
        assert (
            client.patch(
                url, json={"is_active": False}, headers=headers_of(client, who)
            ).status_code
            == 403
        )
    renamed = client.patch(url, json={"label_name": "joinery"}, headers=headers_of(client, owner))
    assert renamed.json()["label_name"] == "joinery"
    client.patch(url, json={"is_active": False}, headers=headers_of(client, owner))

    reader = headers_of(client, others["searcher"])
    names = [label["label_name"] for label in client.get(f"{API}/labels", headers=reader).json()]
    assert "joinery" not in names
    # Only the OWNER may ask for the inactive ones too; for anyone else the flag changes nothing.
    hidden = client.get(f"{API}/labels?include_inactive=true", headers=reader).json()
    assert "joinery" not in [label["label_name"] for label in hidden]
    shown = client.get(f"{API}/labels?include_inactive=true", headers=headers_of(client, owner))
    assert "joinery" in [label["label_name"] for label in shown.json()]


def test_an_applicant_cannot_read_the_labels(client: TestClient, world: World) -> None:
    applicant = add_member(world, "pending")
    response = client.get(f"{API}/labels", headers=headers_of(client, applicant))
    assert (response.status_code, response.json()["error"]["code"]) == (403, "not_admitted")
    searcher = add_member(world, "searcher")
    assert client.get(f"{API}/labels", headers=headers_of(client, searcher)).status_code == 200


# ---- unavailability -----------------------------------------------------------------------


def test_unavailability_crud_and_overlap(client: TestClient, world: World) -> None:
    member = add_member(world, "provider")
    headers = headers_of(client, member)
    url = f"{API}/freelancers/me/unavailability"
    first = client.post(url, json=period(1, 5), headers=headers)
    assert first.status_code == 201
    assert client.post(url, json=period(3, 7), headers=headers).status_code == 409
    second = client.post(url, json=period(10, 12), headers=headers)
    assert second.status_code == 201

    updated = client.put(f"{url}/{first.json()['id']}", json=period(1, 6), headers=headers)
    assert updated.status_code == 200
    clash = client.put(f"{url}/{first.json()['id']}", json=period(9, 11), headers=headers)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "unavailability_overlaps"

    assert len(client.get(url, headers=headers).json()) == 2
    assert client.delete(f"{url}/{second.json()['id']}", headers=headers).status_code == 204
    assert len(client.get(url, headers=headers).json()) == 1


def test_two_people_may_be_unavailable_at_the_same_time(client: TestClient, world: World) -> None:
    one, two = add_member(world, "provider"), add_member(world, "verifier")
    url = f"{API}/freelancers/me/unavailability"
    for who in (one, two):
        assert (
            client.post(url, json=period(1, 5), headers=headers_of(client, who)).status_code == 201
        )


def test_unavailability_validation_and_ownership(client: TestClient, world: World) -> None:
    mine, other = add_member(world, "provider"), add_member(world, "provider")
    url = f"{API}/freelancers/me/unavailability"
    headers = headers_of(client, mine)
    assert client.post(url, json=period(5, 1), headers=headers).status_code == 422
    naive = {"unavailable_from": "2030-01-01T00:00:00", "unavailable_to": "2030-01-02T00:00:00"}
    assert client.post(url, json=naive, headers=headers).status_code == 422

    created = client.post(url, json=period(1, 2), headers=headers).json()
    theirs = headers_of(client, other)
    assert client.delete(f"{url}/{created['id']}", headers=theirs).status_code == 404
    assert (
        client.put(f"{url}/{created['id']}", json=period(1, 3), headers=theirs).status_code == 404
    )


# ---- the rules of the tables ----------------------------------------------------------------


def _label(session: Session, label_type: str, name: str) -> Label:
    found = session.scalar(
        select(Label).where(Label.label_type == label_type, Label.label_name == name)
    )
    assert found is not None
    return found


def test_a_level_belongs_only_to_a_skill_and_must_be_a_level(world: World) -> None:
    session = world.session
    person = world.add_person("provider")
    skill = _label(session, "skill", "plumbing")
    level = _label(session, "skill_level", "basic")
    language = _label(session, "language", "English")
    session.add(PersonLabel(person_id=person.id, label_id=skill.id, level_label_id=level.id))
    session.flush()  # a level on a skill is accepted
    for label_id_, level_id in ((language.id, level.id), (skill.id, language.id)):
        with pytest.raises(DBAPIError), session.begin_nested():
            session.add(
                PersonLabel(person_id=person.id, label_id=label_id_, level_label_id=level_id)
            )
            session.flush()
