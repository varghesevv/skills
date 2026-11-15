"""Mobile number reveal between people: only the reveal endpoint returns a number to a member,
and every reveal is recorded."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.reveals import PersonPhoneReveal
from app.schemas.profiles import RevealRequest
from app.services.reveals import reveal_mobile_number
from tests.api_helpers import API, older_actor
from tests.test_admission import headers_of
from tests.test_person_auth import Member, add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db

BODY = {"channel": "show", "source": "detail", "searched_skills": ["plumbing"]}
MISSING = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def url_of(provider_id: object) -> str:
    return f"{API}/freelancers/{provider_id}/reveal-mobile"


def reveal(
    client: TestClient,
    world: World,
    provider_id: object,
    who: Member,
    body: dict[str, object] | None = None,
) -> Response:
    return client.post(url_of(provider_id), json=body or BODY, headers=headers_of(client, who))


def reveals(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(PersonPhoneReveal)) or 0


def test_a_searcher_reveals_and_it_is_recorded(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider", mobile_number="+971500000321")
    searcher = add_member(world, "searcher")

    response = reveal(client, world, provider.person.id, searcher)

    assert response.status_code == 200
    assert response.json() == {"mobile_number": "+971500000321"}
    assert response.headers["cache-control"] == "no-store"
    row = world.session.scalars(select(PersonPhoneReveal)).one()
    assert (row.revealer_id, row.provider_id) == (searcher.person.id, provider.person.id)
    assert (row.channel, row.source, row.searched_skills) == ("show", "detail", ["plumbing"])


@pytest.mark.parametrize("status", ["searcher", "provider", "verifier", "admin", "owner"])
def test_a_searcher_or_above_may_reveal(client: TestClient, world: World, status: str) -> None:
    provider = add_member(world, "provider")
    assert reveal(client, world, provider.person.id, add_member(world, status)).status_code == 200


def test_an_applicant_may_not(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    response = reveal(client, world, provider.person.id, add_member(world, "pending"))
    assert (response.status_code, response.json()["error"]["code"]) == (403, "not_admitted")
    assert reveals(world.session) == 0


def test_a_revoked_person_may_not(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    member = add_member(world, "searcher")
    headers = headers_of(client, member)
    member.person.status = "revoked"
    member.person.home_group_id = None
    world.session.flush()
    response = client.post(url_of(provider.person.id), json=BODY, headers=headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "account_revoked")
    assert reveals(world.session) == 0


def test_no_token_and_older_account_tokens_are_refused(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    assert client.post(url_of(provider.person.id), json=BODY).status_code == 401
    old = older_actor("workhost")
    assert (
        client.post(url_of(provider.person.id), json=BODY, headers=old.headers).status_code == 401
    )
    assert reveals(world.session) == 0


def test_nobody_reveals_their_own_number(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    response = reveal(client, world, provider.person.id, provider)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "own_number")
    assert reveals(world.session) == 0


def test_only_open_providers_are_revealed(client: TestClient, world: World) -> None:
    searcher = add_member(world, "searcher")
    other_searcher, applicant = add_member(world, "searcher"), add_member(world, "pending")
    revoked, closed = add_member(world, "provider"), add_member(world, "provider")
    revoked.person.status = "revoked"
    revoked.person.home_group_id = None
    closed.person.closed_at = datetime.now(UTC)
    closed.person.home_group_id = None
    closed.person.full_name = closed.person.email = closed.person.mobile_number = None
    closed.person.password_hash = None
    world.session.flush()
    for target in (other_searcher, applicant, revoked, closed):
        assert reveal(client, world, target.person.id, searcher).status_code == 404
    assert reveal(client, world, MISSING, searcher).status_code == 404
    assert reveals(world.session) == 0


@pytest.mark.parametrize(
    "bad",
    [
        {**BODY, "channel": "sms"},
        {**BODY, "source": "email"},
        {**BODY, "searched_skills": ["x"] * 11},
        {**BODY, "searched_skills": ["x" * 101]},
        {"channel": "show"},
    ],
)
def test_bad_input_is_refused_and_nothing_is_recorded(
    client: TestClient, world: World, bad: dict[str, object]
) -> None:
    provider, searcher = add_member(world, "provider"), add_member(world, "searcher")
    assert reveal(client, world, provider.person.id, searcher, bad).status_code == 422
    assert reveals(world.session) == 0


def test_the_number_is_in_no_other_response(client: TestClient, world: World) -> None:
    from tests.test_search_api import provider as searchable

    provider = searchable(world, mobile_number="+971500000777")
    searcher = add_member(world, "searcher")
    reveal(client, world, provider.person.id, searcher)
    headers = headers_of(client, searcher)
    for url in (
        f"{API}/freelancers/{provider.person.id}",
        f"{API}/freelancers/{provider.person.id}/ratings",
        f"{API}/search/freelancers",
    ):
        assert "+971500000777" not in client.get(url, headers=headers).text, url


def test_hourly_limit(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    searcher, other = add_member(world, "searcher"), add_member(world, "searcher")

    for _ in range(3):  # the test limit is 3 per hour
        assert reveal(client, world, provider.person.id, searcher).status_code == 200
    blocked = reveal(client, world, provider.person.id, searcher)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "reveal_limit_reached"
    assert 1 <= int(blocked.headers["retry-after"]) <= 3600
    assert str(provider.person.mobile_number) not in blocked.text
    assert reveals(world.session) == 3
    # The limit is per person.
    assert reveal(client, world, provider.person.id, other).status_code == 200


def test_daily_limit_and_window_slides(client: TestClient, world: World) -> None:
    provider, searcher = add_member(world, "provider"), add_member(world, "searcher")
    for _ in range(3):
        assert reveal(client, world, provider.person.id, searcher).status_code == 200
    # Move those three to 2 hours ago: the hourly window is free again, the daily one is not.
    world.session.execute(
        update(PersonPhoneReveal).values(revealed_at=datetime.now(UTC) - timedelta(hours=2))
    )
    world.session.flush()
    for _ in range(2):  # the test limit is 5 per day
        assert reveal(client, world, provider.person.id, searcher).status_code == 200
    # 3 + 2 = 5 in 24 h: the daily limit is reached, though only 2 were in the last hour.
    blocked = reveal(client, world, provider.person.id, searcher)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 3600

    # After a day the oldest ones no longer count.
    world.session.execute(
        update(PersonPhoneReveal).values(revealed_at=datetime.now(UTC) - timedelta(hours=25))
    )
    world.session.flush()
    assert reveal(client, world, provider.person.id, searcher).status_code == 200


def _stale(world: World, member: Member) -> None:
    """Change the row behind the session's back, as a request running at the same time would."""
    world.session.flush()
    world.session.execute(
        text("UPDATE people SET status = 'revoked', home_group_id = NULL WHERE id = :id"),
        {"id": member.person.id},
    )


def test_a_provider_revoked_meanwhile_is_not_revealed(client: TestClient, world: World) -> None:
    from app.core.config import get_settings

    provider, searcher = add_member(world, "provider"), add_member(world, "searcher")
    assert provider.person.status == "provider"  # the session holds the person as they were
    _stale(world, provider)
    with pytest.raises(ApiError) as caught:
        reveal_mobile_number(
            world.session,
            get_settings(),
            revealer=searcher.person,
            provider_id=provider.person.id,
            body=RevealRequest(channel="show", source="detail"),
        )
    assert (caught.value.status_code, caught.value.code) == (404, "not_found")
    assert reveals(world.session) == 0


def test_a_person_revoked_meanwhile_does_not_reveal(client: TestClient, world: World) -> None:
    from app.core.config import get_settings

    provider, searcher = add_member(world, "provider"), add_member(world, "searcher")
    assert searcher.person.status == "searcher"
    _stale(world, searcher)
    with pytest.raises(ApiError) as caught:
        reveal_mobile_number(
            world.session,
            get_settings(),
            revealer=searcher.person,
            provider_id=provider.person.id,
            body=RevealRequest(channel="show", source="detail"),
        )
    assert (caught.value.status_code, caught.value.code) == (403, "account_revoked")
    assert reveals(world.session) == 0


def test_a_searcher_who_targets_themselves_gets_the_404_of_anyone_who_is_not_a_provider(
    client: TestClient, world: World
) -> None:
    searcher = add_member(world, "searcher")
    assert reveal(client, world, searcher.person.id, searcher).status_code == 404
