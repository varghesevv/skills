"""Freelancer search: filters, sorting, pagination and privacy."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.availability import FreelancerUnavailability
from app.models.labels import FreelancerLabel
from app.models.ratings import UserRating
from app.models.users import Freelancer
from app.models.vouching import OrgFreelancer
from app.services.accounts import create_account
from tests.api_helpers import API, label_id, signup

SEARCH = f"{API}/search/freelancers"


def freelancer(
    session: Session,
    email: str,
    *,
    rate: float | None = 50,
    currency: str = "AED",
    negotiable: bool = False,
    skills: tuple[tuple[str, str | None], ...] = (("plumbing", None),),
    labels: tuple[tuple[str, str], ...] = (),
    full_name: str | None = None,
) -> Freelancer:
    """A freelancer with skills (name, level) and other labels (type, name)."""
    extra: dict[str, object] = {"is_rate_negotiable": negotiable}
    if full_name is not None:
        extra["full_name"] = full_name
    if rate is not None:
        extra.update(rate_per_hour=rate, rate_currency=currency)
    account = create_account(
        session,
        "freelancer",
        email=email,
        mobile_number="+971500000001",
        password=secrets.token_urlsafe(16),
        **extra,
    )
    assert isinstance(account, Freelancer)
    for name, level in skills:
        level_id = uuid.UUID(label_id(session, "skill_level", level)) if level else None
        session.add(
            FreelancerLabel(
                freelancer_id=account.id,
                label_id=uuid.UUID(label_id(session, "skill", name)),
                level_label_id=level_id,
            )
        )
    for label_type, name in labels:
        session.add(
            FreelancerLabel(
                freelancer_id=account.id, label_id=uuid.UUID(label_id(session, label_type, name))
            )
        )
    session.commit()
    return account


def found(client: TestClient, host_headers: dict[str, str], query: str = "") -> list[str]:
    """Ids (as strings) returned by a search, in order."""
    response = client.get(f"{SEARCH}?{query}", headers=host_headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def ids(*accounts: Freelancer) -> set[str]:
    return {str(a.id) for a in accounts}


def test_only_complete_profiles_are_listed(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "sh1@example.com")
    complete = freelancer(session, "c1@example.com")
    freelancer(session, "no-rate@example.com", rate=None)
    freelancer(session, "no-skill@example.com", skills=())
    assert set(found(client, host.headers)) == ids(complete)


def test_skill_filters_any_all_and_level(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "sh2@example.com")
    both = freelancer(
        session, "both@example.com", skills=(("plumbing", "80%"), ("electrical", "basic"))
    )
    plumber = freelancer(session, "plumber@example.com", skills=(("plumbing", "basic"),))
    electrician = freelancer(session, "electrician@example.com", skills=(("electrical", None),))

    assert set(found(client, host.headers, "skill=plumbing")) == ids(both, plumber)
    assert set(found(client, host.headers, "skill=plumbing&skill=electrical")) == ids(
        both, plumber, electrician
    )
    all_skills = "skill=plumbing&skill=electrical&skill_match=all"
    assert set(found(client, host.headers, all_skills)) == ids(both)
    assert set(found(client, host.headers, "skill=plumbing&skill_level=80%25")) == ids(both)
    assert set(found(client, host.headers, "skill=plumbing&skill_level=basic")) == ids(plumber)
    assert set(found(client, host.headers, "skill_level=basic")) == ids(both, plumber)
    # Names are not case sensitive.
    assert set(found(client, host.headers, "skill=PLUMBING")) == ids(both, plumber)


def test_language_timing_and_nativity_filters(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "sh3@example.com")
    a = freelancer(
        session,
        "la@example.com",
        labels=(("language", "English"), ("timing", "24h"), ("nativity", "Keralite")),
    )
    b = freelancer(session, "lb@example.com", labels=(("language", "Hindi"), ("timing", "06-12")))
    c = freelancer(session, "lc@example.com")

    assert set(found(client, host.headers, "language=English")) == ids(a)
    assert set(found(client, host.headers, "language=English&language=Hindi")) == ids(a, b)
    assert set(found(client, host.headers, "timing=24h")) == ids(a)
    assert set(found(client, host.headers, "nativity=keralite")) == ids(a)
    assert set(found(client, host.headers, "language=Hindi&timing=24h")) == set()
    assert set(found(client, host.headers)) == ids(a, b, c)


def test_name_filter_matches_part_of_a_name_in_any_case(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "sh-name@example.com")
    anita = freelancer(session, "anita@example.com", full_name="Anita Sharma")
    ravi = freelancer(session, "ravi@example.com", full_name="Ravi 100%_Kumar")

    assert set(found(client, host.headers, "name=ANITA")) == ids(anita)
    assert set(found(client, host.headers, "name=sharm")) == ids(anita)
    assert set(found(client, host.headers, "name=100%25_")) == ids(ravi)
    assert found(client, host.headers, "name=%25") == [str(ravi.id)]
    assert found(client, host.headers, "name=nobody") == []
    assert set(found(client, host.headers, "name=%20")) == ids(anita, ravi)


def test_rate_currency_and_negotiable_filters(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "sh4@example.com")
    cheap = freelancer(session, "cheap@example.com", rate=20, negotiable=True)
    pricey = freelancer(session, "pricey@example.com", rate=90)
    dollars = freelancer(session, "usd@example.com", rate=10, currency="USD")

    assert set(found(client, host.headers, "max_rate=50&currency=AED")) == ids(cheap)
    assert set(found(client, host.headers, "max_rate=90&currency=aed")) == ids(cheap, pricey)
    assert set(found(client, host.headers, "currency=USD")) == ids(dollars)
    assert set(found(client, host.headers, "negotiable=true")) == ids(cheap)
    no_currency = client.get(f"{SEARCH}?max_rate=50", headers=host.headers)
    assert no_currency.status_code == 422
    assert no_currency.json()["error"]["code"] == "currency_required"


def test_availability_filter_excludes_overlapping_unavailability(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "sh5@example.com")
    free = freelancer(session, "free@example.com")
    busy = freelancer(session, "busy@example.com")
    now = datetime.now(UTC)
    session.add(
        FreelancerUnavailability(
            freelancer_id=busy.id,
            unavailable_from=now + timedelta(days=10),
            unavailable_to=now + timedelta(days=20),
        )
    )
    session.commit()

    def window(start: int, end: int) -> str:
        first = (now + timedelta(days=start)).isoformat().replace("+", "%2B")
        last = (now + timedelta(days=end)).isoformat().replace("+", "%2B")
        return f"available_from={first}&available_to={last}"

    assert set(found(client, host.headers, window(12, 14))) == ids(free)
    assert set(found(client, host.headers, window(1, 5))) == ids(free, busy)
    assert set(found(client, host.headers, window(5, 11))) == ids(free)  # overlaps the start
    assert set(found(client, host.headers, window(20, 25))) == ids(free, busy)  # touches the end
    half = client.get(f"{SEARCH}?{window(1, 2).split('&')[0]}", headers=host.headers)
    assert half.status_code == 422
    backwards = client.get(f"{SEARCH}?{window(5, 1)}", headers=host.headers)
    assert backwards.status_code == 422


def test_vouched_by_filter_counts_only_approved_active_vouches(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "sh6@example.com")
    org = signup(client, session, "organisation", "so1@example.com")
    approved = freelancer(session, "v1@example.com")
    pending = freelancer(session, "v2@example.com")
    revoked = freelancer(session, "v3@example.com")
    session.add_all(
        [
            OrgFreelancer(org_id=org.id, freelancer_id=approved.id, status="approved"),
            OrgFreelancer(org_id=org.id, freelancer_id=pending.id, status="pending"),
            OrgFreelancer(
                org_id=org.id, freelancer_id=revoked.id, status="approved", is_active=False
            ),
        ]
    )
    session.commit()
    assert found(client, host.headers, f"org_id={org.id}") == [str(approved.id)]
    result = client.get(SEARCH, headers=host.headers).json()["items"]
    counts = {item["id"]: item["vouch_count"] for item in result}
    assert counts[str(approved.id)] == 1
    assert counts[str(pending.id)] == 0


def rate_it(session: Session, freelancer_id: uuid.UUID, host_id: uuid.UUID, rating: int) -> None:
    session.add(UserRating(work_host_id=host_id, freelancer_id=freelancer_id, rating=rating))
    session.commit()


def test_rating_filter_and_sorting(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "sh7@example.com")
    other_host = signup(client, session, "workhost", "sh8@example.com")
    best = freelancer(session, "best@example.com", rate=80)
    middle = freelancer(session, "middle@example.com", rate=30)
    unrated = freelancer(session, "unrated@example.com", rate=60)
    rate_it(session, best.id, host.id, 9)
    rate_it(session, best.id, other_host.id, 10)
    rate_it(session, middle.id, host.id, 6)

    assert found(client, host.headers, "sort=rating") == [
        str(best.id),
        str(middle.id),
        str(unrated.id),
    ]
    assert found(client, host.headers, "sort=rate") == [
        str(middle.id),
        str(unrated.id),
        str(best.id),
    ]
    assert set(found(client, host.headers, "min_rating=7")) == ids(best)
    assert set(found(client, host.headers, "min_rating=5")) == ids(best, middle)
    items = client.get(f"{SEARCH}?sort=rating", headers=host.headers).json()["items"]
    assert items[0]["average_rating"] == 9.5
    assert items[0]["rating_count"] == 2
    assert items[2]["average_rating"] is None


def test_newest_is_the_default_order_and_pagination_works(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "sh9@example.com")
    created = [freelancer(session, f"p{i}@example.com") for i in range(5)]
    base = datetime.now(UTC) - timedelta(days=30)
    for index, account in enumerate(created):
        session.execute(
            update(Freelancer)
            .where(Freelancer.id == account.id)
            .values(created_at=base + timedelta(days=index))
        )
    session.commit()

    newest_first = [str(a.id) for a in reversed(created)]
    assert found(client, host.headers) == newest_first
    first = client.get(f"{SEARCH}?page=1&page_size=2", headers=host.headers).json()
    second = client.get(f"{SEARCH}?page=2&page_size=2", headers=host.headers).json()
    last = client.get(f"{SEARCH}?page=3&page_size=2", headers=host.headers).json()
    assert first["total"] == second["total"] == last["total"] == 5
    paged = [i["id"] for i in first["items"] + second["items"] + last["items"]]
    assert paged == newest_first
    assert client.get(f"{SEARCH}?page_size=101", headers=host.headers).status_code == 422
    assert client.get(f"{SEARCH}?sort=best", headers=host.headers).status_code == 422


def test_results_show_labels_and_never_contact_details(
    client: TestClient, session: Session
) -> None:
    host = signup(client, session, "workhost", "sh10@example.com")
    freelancer(
        session,
        "private.person@example.com",
        skills=(("plumbing", "80%"),),
        labels=(("language", "English"), ("timing", "24h"), ("nativity", "Indian")),
    )
    response = client.get(SEARCH, headers=host.headers)
    item = response.json()["items"][0]
    assert item["skills"] == [{"name": "plumbing", "level": "80%"}]
    assert item["languages"] == ["English"]
    assert item["timings"] == ["24h"]
    assert item["nativity"] == ["Indian"]
    assert "private.person" not in response.text
    assert "mobile_number" not in item
    assert "email" not in item


def test_search_is_for_hosts_organisations_and_admins(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "sf1@example.com")
    org = signup(client, session, "organisation", "so2@example.com")
    admin = signup(client, session, "admin", "sadmin@example.com")
    assert client.get(SEARCH).status_code == 401
    assert client.get(SEARCH, headers=me.headers).status_code == 403
    assert client.get(SEARCH, headers=org.headers).status_code == 200
    assert client.get(SEARCH, headers=admin.headers).status_code == 200
