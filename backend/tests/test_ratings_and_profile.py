"""Ratings and the public profile between people (slice S5.2b, decision D-43).

A SEARCHER or above rates and looks at an open PROVIDER or above; anyone else is the same
`404` as someone who does not exist.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PersonUnavailability, Rating
from tests.api_helpers import ghost_actor
from tests.test_admission import headers_of
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db

API = "/api/v1"
MISSING = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def body(provider: Member, rating: int = 8, comment: str | None = "Great") -> dict[str, object]:
    return {"provider_id": str(provider.person.id), "rating": rating, "comment": comment}


def close_account(world: World, member: Member) -> None:
    person = member.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    world.session.flush()


def revoke(world: World, member: Member) -> None:
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()


# ---- rating --------------------------------------------------------------------------------


def test_a_searcher_rates_a_provider_and_changes_it(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider", full_name="Test Person")
    rater = add_member(world, "searcher")
    other = add_member(world, "provider")
    mine, theirs = headers_of(client, rater), headers_of(client, other)

    first = client.post(f"{API}/ratings", json=body(provider), headers=mine)
    assert first.status_code == 201, first.text
    assert first.json()["provider_name"] == "Test Person"
    assert first.json()["provider_id"] == str(provider.person.id)
    assert client.post(f"{API}/ratings", json=body(provider, 4), headers=theirs).status_code == 201

    profile = client.get(f"{API}/freelancers/{provider.person.id}", headers=mine).json()
    assert (profile["average_rating"], profile["rating_count"]) == (6.0, 2)

    url = f"{API}/ratings/{first.json()['id']}"
    changed = client.put(url, json={"rating": 10, "comment": None}, headers=mine)
    assert changed.status_code == 200
    assert (changed.json()["rating"], changed.json()["updated_at"] is not None) == (10, True)
    assert changed.json()["provider_name"] == "Test Person"


def test_one_rating_per_person_and_provider(client: TestClient, world: World) -> None:
    provider, rater = add_member(world, "provider"), add_member(world, "searcher")
    headers = headers_of(client, rater)
    assert client.post(f"{API}/ratings", json=body(provider), headers=headers).status_code == 201
    again = client.post(f"{API}/ratings", json=body(provider, 3), headers=headers)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "already_rated")
    assert world.session.scalar(select(func.count()).select_from(Rating)) == 1


def test_nobody_rates_themselves(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    refused = client.post(
        f"{API}/ratings", json=body(provider), headers=headers_of(client, provider)
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "cannot_rate_self")
    assert world.session.scalar(select(func.count()).select_from(Rating)) == 0


def test_a_searcher_rating_themselves_gets_the_404_of_anyone_who_is_not_a_provider(
    client: TestClient, world: World
) -> None:
    searcher = add_member(world, "searcher")
    response = client.post(
        f"{API}/ratings", json=body(searcher), headers=headers_of(client, searcher)
    )
    assert response.status_code == 404


@pytest.mark.parametrize("status", ["pending", "revoked"])
def test_an_applicant_or_a_revoked_person_does_not_rate(
    client: TestClient, world: World, status: str
) -> None:
    provider = add_member(world, "provider")
    member = add_member(world, "searcher" if status == "revoked" else status)
    headers = headers_of(client, member)
    if status == "revoked":
        revoke(world, member)
    response = client.post(f"{API}/ratings", json=body(provider), headers=headers)
    expected = "account_revoked" if status == "revoked" else "not_admitted"
    assert (response.status_code, response.json()["error"]["code"]) == (403, expected)


def test_only_open_providers_can_be_rated(client: TestClient, world: World) -> None:
    rater = add_member(world, "searcher")
    headers = headers_of(client, rater)
    searcher, applicant = add_member(world, "searcher"), add_member(world, "pending")
    revoked, closed = add_member(world, "provider"), add_member(world, "provider")
    revoke(world, revoked)
    close_account(world, closed)
    for target in (searcher, applicant, revoked, closed):
        response = client.post(f"{API}/ratings", json=body(target), headers=headers)
        assert response.status_code == 404, target.person.status
    unknown = {"provider_id": MISSING, "rating": 5}
    assert client.post(f"{API}/ratings", json=unknown, headers=headers).status_code == 404
    assert world.session.scalar(select(func.count()).select_from(Rating)) == 0


@pytest.mark.parametrize("bad", [0, 11])
def test_a_rating_is_from_1_to_10(client: TestClient, world: World, bad: int) -> None:
    provider, rater = add_member(world, "provider"), add_member(world, "searcher")
    response = client.post(
        f"{API}/ratings", json=body(provider, bad), headers=headers_of(client, rater)
    )
    assert response.status_code == 422


def test_a_rating_can_be_changed_only_by_its_rater(client: TestClient, world: World) -> None:
    provider, rater, other = (
        add_member(world, "provider"),
        add_member(world, "searcher"),
        add_member(world, "searcher"),
    )
    created = client.post(f"{API}/ratings", json=body(provider), headers=headers_of(client, rater))
    url = f"{API}/ratings/{created.json()['id']}"
    assert client.put(url, json={"rating": 1}, headers=headers_of(client, other)).status_code == 404
    assert (
        client.put(url, json={"rating": 1}, headers=headers_of(client, provider)).status_code == 404
    )
    assert (
        client.put(
            f"{API}/ratings/{MISSING}", json={"rating": 1}, headers=headers_of(client, rater)
        ).status_code
        == 404
    )
    kept = world.session.get(Rating, uuid.UUID(created.json()["id"]))
    assert kept is not None and kept.rating == 8


def test_ratings_stay_when_an_account_is_closed(client: TestClient, world: World) -> None:
    provider, rater = add_member(world, "provider"), add_member(world, "searcher")
    client.post(f"{API}/ratings", json=body(provider), headers=headers_of(client, rater))
    close_account(world, rater)
    assert world.session.scalar(select(func.count()).select_from(Rating)) == 1


def test_ratings_given_lists_only_the_callers_own(client: TestClient, world: World) -> None:
    one, two = (
        add_member(world, "provider", full_name="Ann Provider"),
        add_member(world, "provider"),
    )
    rater, other = add_member(world, "searcher"), add_member(world, "searcher")
    mine = headers_of(client, rater)
    client.post(f"{API}/ratings", json=body(one), headers=mine)
    client.post(f"{API}/ratings", json=body(two), headers=headers_of(client, other))
    page = client.get(f"{API}/workhosts/me/ratings", headers=mine).json()
    assert page["total"] == 1
    assert page["items"][0]["provider_name"] == "Ann Provider"
    assert (
        client.get(
            f"{API}/workhosts/me/ratings", headers=headers_of(client, add_member(world, "pending"))
        ).status_code
        == 403
    )


# ---- the public profile --------------------------------------------------------------------


def test_the_profile_shows_church_and_group_and_never_contact_details(
    client: TestClient, world: World
) -> None:
    provider = add_member(world, "provider", nationality="Indian", primary_language="Hindi")
    viewer = add_member(world, "searcher")
    response = client.get(
        f"{API}/freelancers/{provider.person.id}", headers=headers_of(client, viewer)
    )
    assert response.status_code == 200
    shown = response.json()
    assert shown["church"] == {"id": str(world.church.id), "name": world.church.name}
    assert shown["home_group"]["id"] == str(provider.person.home_group_id)
    assert (shown["nationality"], shown["primary_language"]) == ("Indian", "Hindi")
    for hidden in ("email", "mobile_number", "vouched_by"):
        assert hidden not in shown
    assert str(provider.person.mobile_number) not in response.text
    assert provider.email not in response.text


@pytest.mark.parametrize("status", ["provider", "verifier", "admin", "owner"])
def test_providers_and_above_can_be_opened(client: TestClient, world: World, status: str) -> None:
    target = add_member(world, status)
    viewer = headers_of(client, add_member(world, "searcher"))
    assert client.get(f"{API}/freelancers/{target.person.id}", headers=viewer).status_code == 200


def test_who_cannot_be_opened_is_a_404(client: TestClient, world: World) -> None:
    viewer = headers_of(client, add_member(world, "searcher"))
    searcher, applicant = add_member(world, "searcher"), add_member(world, "pending")
    revoked, closed = add_member(world, "provider"), add_member(world, "provider")
    revoke(world, revoked)
    close_account(world, closed)
    for target in (searcher, applicant, revoked, closed):
        for path in ("", "/ratings"):
            response = client.get(f"{API}/freelancers/{target.person.id}{path}", headers=viewer)
            assert response.status_code == 404, (target.person.status, path)
    assert client.get(f"{API}/freelancers/{MISSING}", headers=viewer).status_code == 404


def test_the_profile_needs_a_searcher_or_above(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    url = f"{API}/freelancers/{provider.person.id}"
    assert client.get(url).status_code == 401
    refused = client.get(url, headers=headers_of(client, add_member(world, "pending")))
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "not_admitted")
    ratings = client.get(url + "/ratings", headers=headers_of(client, add_member(world, "pending")))
    assert ratings.status_code == 403


def test_the_profile_shows_upcoming_unavailability_only(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    now = datetime.now(UTC)
    for start, end in ((-10, -5), (5, 9)):  # one in the past, one to come
        world.session.add(
            PersonUnavailability(
                person_id=provider.person.id,
                unavailable_from=now + timedelta(days=start),
                unavailable_to=now + timedelta(days=end),
            )
        )
    world.session.flush()
    viewer = headers_of(client, add_member(world, "searcher"))
    shown = client.get(f"{API}/freelancers/{provider.person.id}", headers=viewer).json()
    assert len(shown["unavailable"]) == 1


def test_the_profile_shows_my_rating_to_me_only(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider", full_name="Rated Person")
    one, two = add_member(world, "searcher"), add_member(world, "searcher")
    url = f"{API}/freelancers/{provider.person.id}"
    assert client.get(url, headers=headers_of(client, one)).json()["my_rating"] is None
    created = client.post(
        f"{API}/ratings", json=body(provider, 7, "Fine"), headers=headers_of(client, one)
    ).json()
    mine = client.get(url, headers=headers_of(client, one)).json()["my_rating"]
    assert mine["id"] == created["id"]
    assert (mine["rating"], mine["comment"], mine["provider_name"]) == (7, "Fine", "Rated Person")
    assert client.get(url, headers=headers_of(client, two)).json()["my_rating"] is None


def test_the_ratings_list_hides_who_rated(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    for _ in range(2):
        rater = add_member(world, "searcher")
        client.post(f"{API}/ratings", json=body(provider), headers=headers_of(client, rater))
    page = client.get(
        f"{API}/freelancers/{provider.person.id}/ratings", headers=headers_of(client, provider)
    ).json()
    assert page["total"] == 2
    assert all(set(item) == {"rating", "comment", "rated_on"} for item in page["items"])


def test_older_account_tokens_open_none_of_it(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    old = ghost_actor()
    for method, path in (
        ("GET", f"/freelancers/{provider.person.id}"),
        ("GET", f"/freelancers/{provider.person.id}/ratings"),
        ("POST", f"/freelancers/{provider.person.id}/reveal-mobile"),
        ("POST", "/ratings"),
        ("GET", "/workhosts/me/ratings"),
    ):
        response = client.request(method, f"{API}{path}", headers=old.headers, json={})
        assert response.status_code == 401, path
