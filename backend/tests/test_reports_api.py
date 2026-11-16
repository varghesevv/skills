"""Report endpoints: on-demand reports, stored runs, downloads and schedules.

Reports are for the OWNER (every church) and an ADMIN (their own church, always). Run history,
kept files and schedules are the OWNER's alone.
"""

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.church import Church, HomeGroup, Person
from app.models.reports import ReportRun
from tests.api_helpers import API, ghost_actor
from tests.test_admission import headers_of, owner_member
from tests.test_person_auth import Member, add_member
from tests.test_search_api import provider
from tests.trust_helpers import World, make_person

pytestmark = pytest.mark.db

REPORTS = f"{API}/reports"
SCOPED = {
    "registrations_per_day",
    "providers_by_label",
    "verification_summary",
    "availability_overview",
    "trust_events",
}


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture
def reports_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def admin_of(world: World, church: Church, group: HomeGroup) -> Member:
    """The ADMIN of a second church (the first church's ADMIN is the OWNER), with a password."""
    admin = world.session.get(Person, church.admin_id)
    assert admin is not None and group.leader_id == admin.id
    password = secrets.token_urlsafe(16)
    admin.password_hash = hash_password(password)
    world.session.flush()
    return Member(admin, password)


def second_church(world: World) -> tuple[Church, Member]:
    church, group, _ = world.add_church("Hope Church")
    return church, admin_of(world, church, group)


# ---- who may read -------------------------------------------------------------------------


def test_the_owner_lists_every_report(client: TestClient, world: World) -> None:
    owner = owner_member(world)
    everything = client.get(REPORTS, headers=headers_of(client, owner)).json()
    assert len(everything) == 14
    assert {"RP-01", "RP-09", "RP-10", "RP-11", "SC-01"} <= {report["code"] for report in everything}


def test_an_admin_lists_only_the_reports_limited_to_their_church(
    client: TestClient, world: World
) -> None:
    _, admin = second_church(world)
    listed = client.get(REPORTS, headers=headers_of(client, admin)).json()
    assert {report["name"] for report in listed} == SCOPED


@pytest.mark.parametrize("status", ["pending", "searcher", "provider", "verifier"])
def test_nobody_below_an_admin_reads_reports(client: TestClient, world: World, status: str) -> None:
    headers = headers_of(client, add_member(world, status))
    refused = client.get(REPORTS, headers=headers)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "not_admitted")
    assert client.get(f"{REPORTS}/trust_events", headers=headers).status_code == 403


def test_no_token_and_older_account_tokens_read_nothing(client: TestClient, world: World) -> None:
    assert client.get(REPORTS).status_code == 401
    old = ghost_actor()
    assert client.get(REPORTS, headers=old.headers).status_code == 401


def test_an_admin_runs_only_reports_limited_to_their_church(
    client: TestClient, world: World
) -> None:
    _, admin = second_church(world)
    headers = headers_of(client, admin)
    for name in ("active_users", "top_rated", "rate_distribution", "phone_reveals"):
        response = client.get(f"{REPORTS}/{name}", headers=headers)
        assert response.status_code == 403, name
    assert client.get(f"{REPORTS}/trust_events", headers=headers).status_code == 200


def test_an_admin_always_gets_their_own_church_whatever_they_ask_for(
    client: TestClient, world: World
) -> None:
    other_church, admin = second_church(world)
    add_member(world, "searcher")  # a person of the OWNER's church
    group = world.session.scalars(
        select(HomeGroup).where(HomeGroup.church_id == other_church.id)
    ).one()
    world.session.add(make_person(other_church, group, "searcher"))
    world.session.flush()
    today = datetime.now(UTC).date()
    window = f"from={today - timedelta(days=2)}&to={today + timedelta(days=2)}"
    own = client.get(
        f"{REPORTS}/registrations_per_day?{window}", headers=headers_of(client, admin)
    ).json()
    assert {row[1] for row in own["sections"][0]["rows"]} == {"Hope Church"}
    asking = client.get(
        f"{REPORTS}/registrations_per_day?{window}&church_id={world.church.id}",
        headers=headers_of(client, admin),
    ).json()
    assert {row[1] for row in asking["sections"][0]["rows"]} == {"Hope Church"}
    owner = owner_member(world)
    everyone = client.get(
        f"{REPORTS}/registrations_per_day?{window}", headers=headers_of(client, owner)
    ).json()
    assert {row[1] for row in everyone["sections"][0]["rows"]} == {world.church.name, "Hope Church"}
    narrowed = client.get(
        f"{REPORTS}/registrations_per_day?{window}&church_id={other_church.id}",
        headers=headers_of(client, owner),
    ).json()
    assert {row[1] for row in narrowed["sections"][0]["rows"]} == {"Hope Church"}


# ---- running ------------------------------------------------------------------------------


def test_on_demand_report_as_json_and_csv(client: TestClient, world: World) -> None:
    owner = owner_member(world)
    headers = headers_of(client, owner)
    provider(world)
    url = f"{REPORTS}/registrations_per_day?from=2000-01-01&to=2000-01-31"
    as_json = client.get(url, headers=headers)
    assert as_json.status_code == 200
    body = as_json.json()
    assert body["name"] == "registrations_per_day"
    assert body["sections"][0]["columns"] == ["day", "church", "status_now", "sign_ups"]
    assert body["row_count"] == 0

    csv = client.get(f"{REPORTS}/providers_by_label?format=csv", headers=headers)
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv.headers["content-disposition"]
    assert csv.text.splitlines()[0] == "label_type,label,providers"
    assert "skill,plumbing,1" in csv.text


def test_on_demand_report_validation(client: TestClient, world: World) -> None:
    headers = headers_of(client, owner_member(world))
    assert client.get(f"{REPORTS}/nope", headers=headers).status_code == 404
    assert client.get(f"{REPORTS}/active_users?from=2026-10-01", headers=headers).status_code == 422
    backwards = client.get(f"{REPORTS}/active_users?from=2026-10-05&to=2026-10-01", headers=headers)
    assert backwards.status_code == 422
    too_long = client.get(
        f"{REPORTS}/availability_overview?from=2026-01-01&to=2026-12-31", headers=headers
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "report_error"
    bad_status = client.get(f"{REPORTS}/active_users?status=wizard", headers=headers)
    assert bad_status.status_code == 422


def test_reports_hold_no_names_emails_or_numbers(client: TestClient, world: World) -> None:
    owner = owner_member(world)
    target = provider(world, full_name="Zed Secretname", mobile_number="+971500099999")
    rater = add_member(world, "searcher")
    headers = headers_of(client, rater)
    client.post(
        f"{API}/ratings",
        json={"provider_id": str(target.person.id), "rating": 9},
        headers=headers,
    )
    client.post(
        f"{API}/freelancers/{target.person.id}/reveal-mobile",
        json={"channel": "show", "source": "detail"},
        headers=headers,
    )
    for name in ("top_rated", "phone_reveals", "verification_summary", "trust_events"):
        text = client.get(f"{REPORTS}/{name}", headers=headers_of(client, owner)).text
        for secret in ("Zed Secretname", "+971500099999", target.email, str(target.person.id)):
            assert secret not in text, (name, secret)


def test_csv_does_not_run_formulas(client: TestClient, world: World) -> None:
    owner = owner_member(world)
    world.church.name = "=HYPERLINK(1)"
    world.session.flush()
    csv = client.get(
        f"{REPORTS}/verification_summary?format=csv", headers=headers_of(client, owner)
    )
    assert "'=HYPERLINK(1)" in csv.text
    assert ",=HYPERLINK" not in csv.text


# ---- the OWNER's run history, files and schedules ------------------------------------------


def test_run_store_list_and_download(client: TestClient, world: World, reports_dir: Path) -> None:
    owner = owner_member(world)
    headers = headers_of(client, owner)
    _, admin = second_church(world)
    body = {"date_from": "2026-10-20", "date_to": "2026-10-21"}
    url = f"{REPORTS}/signups_daily/run"

    assert client.post(url, json=body, headers=headers_of(client, admin)).status_code == 403
    created = client.post(url, json=body, headers=headers)
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "succeeded"
    assert run["has_files"] is True
    repeated = client.post(url, json=body, headers=headers)
    assert repeated.status_code == 200  # nothing ran again
    assert repeated.json()["id"] == run["id"]

    runs_url = f"{REPORTS}/runs?report_name=signups_daily"
    assert client.get(runs_url, headers=headers).json()["total"] == 1
    assert client.get(f"{REPORTS}/runs", headers=headers_of(client, admin)).status_code == 403

    csv = client.get(f"{REPORTS}/runs/{run['id']}/download", headers=headers)
    assert csv.status_code == 200
    assert "New applicants by church and requested status" in csv.text
    assert (
        client.get(
            f"{REPORTS}/runs/{run['id']}/download", headers=headers_of(client, admin)
        ).status_code
        == 403
    )
    html = client.get(f"{REPORTS}/runs/{run['id']}/download?format=html", headers=headers)
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<table>" in html.text

    backwards = {"date_from": "2026-10-21", "date_to": "2026-10-20"}
    assert client.post(url, json=backwards, headers=headers).status_code == 422
    assert client.post(f"{REPORTS}/nope/run", json=body, headers=headers).status_code == 404


def test_download_cannot_leave_the_output_folder(
    client: TestClient, world: World, reports_dir: Path
) -> None:
    headers = headers_of(client, owner_member(world))
    body = {"date_from": "2026-10-20", "date_to": "2026-10-20"}
    run = client.post(f"{REPORTS}/active_users/run", json=body, headers=headers).json()
    row = world.session.get(ReportRun, run["id"])
    assert row is not None
    row.file_path = "../../../../etc/passwd"
    world.session.flush()
    assert client.get(f"{REPORTS}/runs/{run['id']}/download", headers=headers).status_code == 404


def test_download_needs_a_finished_run(client: TestClient, world: World) -> None:
    headers = headers_of(client, owner_member(world))
    missing = f"{REPORTS}/runs/00000000-0000-4000-8000-000000000000/download"
    assert client.get(missing, headers=headers).status_code == 404


def test_schedules_can_be_listed_and_changed_by_the_owner_only(
    client: TestClient, world: World
) -> None:
    headers = headers_of(client, owner_member(world))
    _, admin = second_church(world)
    mine = headers_of(client, admin)
    schedules = client.get(f"{REPORTS}/schedules", headers=headers).json()
    assert {s["report_name"] for s in schedules} == {
        "signups_daily",
        "weekly_summary",
        "monthly_summary",
    }
    daily = next(s for s in schedules if s["report_name"] == "signups_daily")
    assert (daily["cron_expression"], daily["timezone"]) == ("5 0 * * *", "Asia/Dubai")
    assert client.get(f"{REPORTS}/schedules", headers=mine).status_code == 403

    url = f"{REPORTS}/schedules/signups_daily"
    change = {"cron_expression": "30 1 * * *", "timezone": "Asia/Dubai", "is_enabled": False}
    assert client.put(url, json=change, headers=mine).status_code == 403
    updated = client.put(url, json=change, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["is_enabled"] is False

    for bad in (
        {**change, "cron_expression": "every day please"},
        {**change, "cron_expression": "99 99 * * *"},
        {**change, "timezone": "Mars/Base"},
    ):
        assert client.put(url, json=bad, headers=headers).status_code == 422
    unknown = f"{REPORTS}/schedules/not_a_report"
    assert client.put(unknown, json=change, headers=headers).status_code == 404
