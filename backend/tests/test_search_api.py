"""Provider search: filters, sorting, pagination, who may search and who is listed."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Person, PersonLabel, PersonUnavailability, Rating
from tests.api_helpers import API, label_id, older_actor
from tests.test_admission import headers_of
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db

SEARCH = f"{API}/search/freelancers"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def provider(
    world: World,
    *,
    status: str = "provider",
    rate: float | None = 50,
    currency: str = "AED",
    negotiable: bool = False,
    skills: tuple[tuple[str, str | None], ...] = (("plumbing", None),),
    labels: tuple[tuple[str, str], ...] = (),
    full_name: str | None = None,
    **extra: object,
) -> Member:
    """A person with skills (name, level) and other labels (type, name), in the first group."""
    values: dict[str, object] = {"is_rate_negotiable": negotiable, **extra}
    if full_name is not None:
        values["full_name"] = full_name
    if rate is not None:
        values.update(rate_per_hour=rate, rate_currency=currency)
    member = add_member(world, status, **values)
    session = world.session
    for name, level in skills:
        level_id = uuid.UUID(label_id(session, "skill_level", level)) if level else None
        session.add(
            PersonLabel(
                person_id=member.person.id,
                label_id=uuid.UUID(label_id(session, "skill", name)),
                level_label_id=level_id,
            )
        )
    for label_type, name in labels:
        session.add(
            PersonLabel(
                person_id=member.person.id,
                label_id=uuid.UUID(label_id(session, label_type, name)),
            )
        )
    session.flush()
    return member


def viewer(client: TestClient, world: World) -> dict[str, str]:
    """Headers of a SEARCHER, who looks at the others."""
    return headers_of(client, add_member(world, "searcher"))


def found(client: TestClient, headers: dict[str, str], query: str = "") -> list[str]:
    """Ids (as strings) returned by a search, in order."""
    response = client.get(f"{SEARCH}?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def ids(*members: Member) -> set[str]:
    return {str(m.person.id) for m in members}


# ---- who may search, who is listed --------------------------------------------------------


def test_a_skill_is_needed_but_a_rate_and_ratings_are_not(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    with_rate = provider(world)
    newcomer = provider(world, rate=None)
    provider(world, skills=())
    assert set(found(client, headers)) == ids(with_rate, newcomer)
    # Without a rate they never match a rate filter, and come last when sorted by rate.
    assert found(client, headers, "max_rate=100&currency=AED") == [str(with_rate.person.id)]
    assert found(client, headers, "sort=rate") == [
        str(with_rate.person.id),
        str(newcomer.person.id),
    ]


@pytest.mark.parametrize("status", ["provider", "verifier", "admin", "owner"])
def test_providers_and_above_are_listed(client: TestClient, world: World, status: str) -> None:
    headers = viewer(client, world)
    member = provider(world, status=status)
    assert str(member.person.id) in found(client, headers)


@pytest.mark.parametrize("status", ["pending", "searcher"])
def test_applicants_and_searchers_are_not_listed_even_with_a_skill(
    client: TestClient, world: World, status: str
) -> None:
    headers = viewer(client, world)
    hidden = provider(world, status=status)
    shown = provider(world)
    assert found(client, headers) == [str(shown.person.id)]
    assert str(hidden.person.id) not in found(client, headers, "skill=plumbing")


def test_a_revoked_person_is_not_listed(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    gone = provider(world)
    gone.person.status = "revoked"
    gone.person.home_group_id = None
    world.session.flush()
    assert found(client, headers) == []


def test_a_closed_account_is_not_listed(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    closed = provider(world)
    person = closed.person
    person.closed_at = datetime.now(UTC)
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    world.session.flush()
    assert found(client, headers) == []


def test_an_applicant_may_not_search(client: TestClient, world: World) -> None:
    headers = headers_of(client, add_member(world, "pending"))
    response = client.get(SEARCH, headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "not_admitted")


def test_a_person_revoked_after_logging_in_may_not_search(client: TestClient, world: World) -> None:
    member = add_member(world, "searcher")
    headers = headers_of(client, member)
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.get(SEARCH, headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")


def test_search_needs_a_token_and_a_person(client: TestClient, world: World) -> None:
    assert client.get(SEARCH).status_code == 401
    old = older_actor("workhost")
    assert client.get(SEARCH, headers=old.headers).status_code == 401
    assert client.get(SEARCH, headers=viewer(client, world)).status_code == 200


# ---- filters -----------------------------------------------------------------------------


def test_skill_filters_any_all_and_level(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    both = provider(world, skills=(("plumbing", "80%"), ("electrical", "basic")))
    plumber = provider(world, skills=(("plumbing", "basic"),))
    electrician = provider(world, skills=(("electrical", None),))

    assert set(found(client, headers, "skill=plumbing")) == ids(both, plumber)
    assert set(found(client, headers, "skill=plumbing&skill=electrical")) == ids(
        both, plumber, electrician
    )
    all_skills = "skill=plumbing&skill=electrical&skill_match=all"
    assert set(found(client, headers, all_skills)) == ids(both)
    assert set(found(client, headers, "skill=plumbing&skill_level=80%25")) == ids(both)
    assert set(found(client, headers, "skill=plumbing&skill_level=basic")) == ids(plumber)
    assert set(found(client, headers, "skill_level=basic")) == ids(both, plumber)
    # Names are not case sensitive.
    assert set(found(client, headers, "skill=PLUMBING")) == ids(both, plumber)


def test_language_timing_and_nativity_filters(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    a = provider(
        world, labels=(("language", "English"), ("timing", "24h"), ("nativity", "Keralite"))
    )
    b = provider(world, labels=(("language", "Hindi"), ("timing", "06-12")))
    c = provider(world)

    assert set(found(client, headers, "language=English")) == ids(a)
    assert set(found(client, headers, "language=English&language=Hindi")) == ids(a, b)
    assert set(found(client, headers, "timing=24h")) == ids(a)
    assert set(found(client, headers, "nativity=keralite")) == ids(a)
    assert set(found(client, headers, "language=Hindi&timing=24h")) == set()
    assert set(found(client, headers)) == ids(a, b, c)


def test_name_filter_matches_part_of_a_name_in_any_case(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    anita = provider(world, full_name="Anita Sharma")
    ravi = provider(world, full_name="Ravi 100%_Kumar")

    assert set(found(client, headers, "name=ANITA")) == ids(anita)
    assert set(found(client, headers, "name=sharm")) == ids(anita)
    assert set(found(client, headers, "name=100%25_")) == ids(ravi)
    assert found(client, headers, "name=%25") == [str(ravi.person.id)]
    assert found(client, headers, "name=nobody") == []
    assert set(found(client, headers, "name=%20")) == ids(anita, ravi)


def test_rate_currency_and_negotiable_filters(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    cheap = provider(world, rate=20, negotiable=True)
    pricey = provider(world, rate=90)
    dollars = provider(world, rate=10, currency="USD")

    assert set(found(client, headers, "max_rate=50&currency=AED")) == ids(cheap)
    assert set(found(client, headers, "max_rate=90&currency=aed")) == ids(cheap, pricey)
    assert set(found(client, headers, "currency=USD")) == ids(dollars)
    assert set(found(client, headers, "negotiable=true")) == ids(cheap)
    no_currency = client.get(f"{SEARCH}?max_rate=50", headers=headers)
    assert no_currency.status_code == 422
    assert no_currency.json()["error"]["code"] == "currency_required"


def test_availability_filter_excludes_overlapping_unavailability(
    client: TestClient, world: World
) -> None:
    headers = viewer(client, world)
    free = provider(world)
    busy = provider(world)
    now = datetime.now(UTC)
    world.session.add(
        PersonUnavailability(
            person_id=busy.person.id,
            unavailable_from=now + timedelta(days=10),
            unavailable_to=now + timedelta(days=20),
        )
    )
    world.session.flush()

    def window(start: int, end: int) -> str:
        first = (now + timedelta(days=start)).isoformat().replace("+", "%2B")
        last = (now + timedelta(days=end)).isoformat().replace("+", "%2B")
        return f"available_from={first}&available_to={last}"

    assert set(found(client, headers, window(12, 14))) == ids(free)
    assert set(found(client, headers, window(1, 5))) == ids(free, busy)
    assert set(found(client, headers, window(5, 11))) == ids(free)  # overlaps the start
    assert set(found(client, headers, window(20, 25))) == ids(free, busy)  # touches the end
    half = client.get(f"{SEARCH}?{window(1, 2).split('&')[0]}", headers=headers)
    assert half.status_code == 422
    backwards = client.get(f"{SEARCH}?{window(5, 1)}", headers=headers)
    assert backwards.status_code == 422


def test_church_and_home_group_filters(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    here = provider(world)
    church_two, group_two, admin_two = world.add_church("Hope Church")
    admin_two.rate_per_hour = None
    there = provider(world, skills=(("plumbing", None),))
    there.person.church_id = church_two.id
    there.person.home_group_id = group_two.id
    world.session.flush()

    assert set(found(client, headers)) >= ids(here, there)  # every church is searched
    assert set(found(client, headers, f"church_id={church_two.id}")) == ids(there)
    assert set(found(client, headers, f"home_group_id={group_two.id}")) == ids(there)
    assert set(found(client, headers, f"church_id={world.church.id}")) == ids(here)
    assert found(client, headers, f"church_id={church_two.id}&home_group_id={world.group.id}") == []
    # The older filter by organisation is gone: a query string it was in changes nothing.
    assert set(found(client, headers, f"org_id={uuid.uuid4()}")) == set(found(client, headers))


# ---- ratings, order, pages ---------------------------------------------------------------


def rate_it(world: World, provider_id: uuid.UUID, rater: Member, rating: int) -> None:
    world.session.add(Rating(rater_id=rater.person.id, provider_id=provider_id, rating=rating))
    world.session.flush()


def test_rating_filter_and_sorting(client: TestClient, world: World) -> None:
    one, two = add_member(world, "searcher"), add_member(world, "searcher")
    headers = headers_of(client, one)
    best = provider(world, rate=80)
    middle = provider(world, rate=30)
    unrated = provider(world, rate=60)
    rate_it(world, best.person.id, one, 9)
    rate_it(world, best.person.id, two, 10)
    rate_it(world, middle.person.id, one, 6)

    assert found(client, headers, "sort=rating") == [
        str(best.person.id),
        str(middle.person.id),
        str(unrated.person.id),
    ]
    assert found(client, headers, "sort=rate") == [
        str(middle.person.id),
        str(unrated.person.id),
        str(best.person.id),
    ]
    assert set(found(client, headers, "min_rating=7")) == ids(best)
    assert set(found(client, headers, "min_rating=5")) == ids(best, middle)
    items = client.get(f"{SEARCH}?sort=rating", headers=headers).json()["items"]
    assert items[0]["average_rating"] == 9.5
    assert items[0]["rating_count"] == 2
    assert items[2]["average_rating"] is None


def test_newest_is_the_default_order_and_pagination_works(client: TestClient, world: World) -> None:
    headers = viewer(client, world)
    created = [provider(world) for _ in range(5)]
    base = datetime.now(UTC) - timedelta(days=30)
    for index, member in enumerate(created):
        world.session.execute(
            update(Person)
            .where(Person.id == member.person.id)
            .values(created_at=base + timedelta(days=index))
        )
    world.session.flush()

    newest_first = [str(m.person.id) for m in reversed(created)]
    assert found(client, headers) == newest_first
    first = client.get(f"{SEARCH}?page=1&page_size=2", headers=headers).json()
    second = client.get(f"{SEARCH}?page=2&page_size=2", headers=headers).json()
    last = client.get(f"{SEARCH}?page=3&page_size=2", headers=headers).json()
    assert first["total"] == second["total"] == last["total"] == 5
    paged = [i["id"] for i in first["items"] + second["items"] + last["items"]]
    assert paged == newest_first
    assert client.get(f"{SEARCH}?page_size=101", headers=headers).status_code == 422
    assert client.get(f"{SEARCH}?sort=best", headers=headers).status_code == 422


def test_results_show_labels_the_church_and_group_and_never_contact_details(
    client: TestClient, world: World
) -> None:
    headers = viewer(client, world)
    member = provider(
        world,
        skills=(("plumbing", "80%"),),
        labels=(("language", "English"), ("timing", "24h"), ("nativity", "Indian")),
    )
    response = client.get(SEARCH, headers=headers)
    item = response.json()["items"][0]
    assert item["skills"] == [{"name": "plumbing", "level": "80%"}]
    assert item["languages"] == ["English"]
    assert item["timings"] == ["24h"]
    assert item["nativity"] == ["Indian"]
    assert item["church"] == {"id": str(world.church.id), "name": world.church.name}
    assert item["home_group"]["id"] == str(member.person.home_group_id)
    assert member.email not in response.text
    assert str(member.person.mobile_number) not in response.text
    assert "mobile_number" not in item and "email" not in item
    assert "vouch_count" not in item
