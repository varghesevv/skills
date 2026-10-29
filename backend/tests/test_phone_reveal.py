"""Mobile number reveal: only the reveal endpoint returns a number, every reveal is recorded."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.reveals import PhoneReveal
from tests.api_helpers import API, Actor, signup

NUMBER = "+971500000099"  # the number signup() gives every account
BODY = {"channel": "show", "source": "detail", "searched_skills": ["plumbing"]}


def reveal(
    client: TestClient, freelancer_id: object, actor: Actor, body: dict[str, object] | None = None
) -> Response:
    return client.post(reveal_url(freelancer_id), json=body or BODY, headers=actor.headers)


def reveal_url(freelancer_id: object) -> str:
    return f"{API}/freelancers/{freelancer_id}/reveal-mobile"


def test_work_host_reveals_and_it_is_recorded(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv1@example.com")
    host = signup(client, session, "workhost", "rvh1@example.com")

    response = reveal(client, freelancer.id, host)

    assert response.status_code == 200
    assert response.json() == {"mobile_number": NUMBER}
    assert response.headers["cache-control"] == "no-store"
    row = session.scalars(select(PhoneReveal)).one()
    assert (row.work_host_id, row.freelancer_id) == (host.id, freelancer.id)
    assert (row.channel, row.source, row.searched_skills) == ("show", "detail", ["plumbing"])


def test_nobody_else_can_reveal(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv2@example.com")
    other = signup(client, session, "freelancer", "rv2b@example.com")
    org = signup(client, session, "organisation", "rvo2@example.com")
    admin = signup(client, session, "admin", "rva2@example.com")

    for actor in (other, org, admin):
        assert reveal(client, freelancer.id, actor).status_code == 403
    assert client.post(reveal_url(freelancer.id), json=BODY).status_code == 401
    assert session.scalar(select(func.count()).select_from(PhoneReveal)) == 0


def test_number_is_in_no_other_response(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv3@example.com")
    host = signup(client, session, "workhost", "rvh3@example.com")
    admin = signup(client, session, "admin", "rva3@example.com")
    reveal(client, freelancer.id, host)

    urls = (
        f"{API}/freelancers/{freelancer.id}",
        f"{API}/freelancers/{freelancer.id}/ratings",
        f"{API}/search/freelancers",
    )
    for actor in (host, admin):
        for url in urls:
            response = client.get(url, headers=actor.headers)
            assert NUMBER not in response.text, url
    assert "mobile" not in client.get(urls[2], headers=host.headers).text


def test_unknown_freelancer_and_bad_input(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv4@example.com")
    host = signup(client, session, "workhost", "rvh4@example.com")

    assert reveal(client, "00000000-0000-4000-8000-000000000000", host).status_code == 404
    for bad in (
        {**BODY, "channel": "sms"},
        {**BODY, "source": "email"},
        {**BODY, "searched_skills": ["x"] * 11},
        {**BODY, "searched_skills": ["x" * 101]},
        {"channel": "show"},
    ):
        response = reveal(client, freelancer.id, host, bad)
        assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(PhoneReveal)) == 0


def test_hourly_limit(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv5@example.com")
    host = signup(client, session, "workhost", "rvh5@example.com")
    other_host = signup(client, session, "workhost", "rvh5b@example.com")

    for _ in range(3):  # the test limit is 3 per hour
        assert reveal(client, freelancer.id, host).status_code == 200
    blocked = reveal(client, freelancer.id, host)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "reveal_limit_reached"
    assert 1 <= int(blocked.headers["retry-after"]) <= 3600
    assert NUMBER not in blocked.text
    assert session.scalar(select(func.count()).select_from(PhoneReveal)) == 3
    # The limit is per work host.
    assert reveal(client, freelancer.id, other_host).status_code == 200


def test_daily_limit_and_window_slides(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "rv6@example.com")
    host = signup(client, session, "workhost", "rvh6@example.com")
    for _ in range(3):
        assert reveal(client, freelancer.id, host).status_code == 200
    # Move those three to 2 hours ago: the hourly window is free again, the daily one is not.
    session.execute(update(PhoneReveal).values(revealed_at=datetime.now(UTC) - timedelta(hours=2)))
    session.commit()
    for _ in range(2):  # the test limit is 5 per day
        assert reveal(client, freelancer.id, host).status_code == 200
    # 3 + 2 = 5 in 24 h: the daily limit is reached, though only 2 were in the last hour.
    blocked = reveal(client, freelancer.id, host)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 3600

    # After a day the oldest ones no longer count.
    session.execute(update(PhoneReveal).values(revealed_at=datetime.now(UTC) - timedelta(hours=25)))
    session.commit()
    assert reveal(client, freelancer.id, host).status_code == 200
