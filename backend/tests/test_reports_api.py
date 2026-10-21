"""Report endpoints: on-demand reports, stored runs, downloads and schedules."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.reports import ReportRun
from app.models.vouching import OrgFreelancer
from tests.api_helpers import API, signup
from tests.test_search_api import freelancer

REPORTS = f"{API}/reports"
WINDOW = "from=2026-10-20&to=2026-10-21"


@pytest.fixture
def reports_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_who_can_list_reports(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra1@example.com")
    org = signup(client, session, "organisation", "ro1@example.com")
    me = signup(client, session, "freelancer", "rf1@example.com")
    everything = client.get(REPORTS, headers=admin.headers).json()
    assert len(everything) == 10
    assert {"RP-01", "RP-07", "SC-01"} <= {report["code"] for report in everything}
    scoped = client.get(REPORTS, headers=org.headers).json()
    assert [report["name"] for report in scoped] == ["vouching_summary"]
    assert client.get(REPORTS, headers=me.headers).status_code == 403
    assert client.get(REPORTS).status_code == 401


def test_on_demand_report_as_json_and_csv(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra2@example.com")
    freelancer(session, "rr1@example.com")
    url = f"{REPORTS}/registrations_per_day?from=2000-01-01&to=2000-01-31"
    as_json = client.get(url, headers=admin.headers)
    assert as_json.status_code == 200
    body = as_json.json()
    assert body["name"] == "registrations_per_day"
    assert body["sections"][0]["columns"] == ["day", "user_type", "registrations"]
    assert body["row_count"] == 0

    csv = client.get(f"{REPORTS}/freelancers_by_label?format=csv", headers=admin.headers)
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv.headers["content-disposition"]
    assert csv.text.splitlines()[0] == "label_type,label,freelancers"
    assert "skill,plumbing,1" in csv.text


def test_on_demand_report_validation(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra3@example.com")
    headers = admin.headers
    assert client.get(f"{REPORTS}/nope", headers=headers).status_code == 404
    assert client.get(f"{REPORTS}/active_users?from=2026-10-01", headers=headers).status_code == 422
    backwards = client.get(f"{REPORTS}/active_users?from=2026-10-05&to=2026-10-01", headers=headers)
    assert backwards.status_code == 422
    too_long = client.get(
        f"{REPORTS}/availability_overview?from=2026-01-01&to=2026-12-31", headers=headers
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "report_error"


def test_organisation_sees_only_its_own_vouching_data(client: TestClient, session: Session) -> None:
    mine = signup(client, session, "organisation", "ro2@example.com", org_name="Mine Ltd")
    other = signup(client, session, "organisation", "ro3@example.com", org_name="Other Ltd")
    person = freelancer(session, "ro-person@example.com")
    session.add(OrgFreelancer(org_id=mine.id, freelancer_id=person.id, status="approved"))
    session.commit()

    url = f"{REPORTS}/vouching_summary?org_id={other.id}"  # asking for someone else's data
    body = client.get(url, headers=mine.headers).json()
    assert [row[1] for row in body["sections"][0]["rows"]] == ["Mine Ltd"]
    assert client.get(f"{REPORTS}/active_users", headers=mine.headers).status_code == 403

    admin = signup(client, session, "admin", "ra4@example.com")
    everyone = client.get(f"{REPORTS}/vouching_summary", headers=admin.headers).json()
    assert len(everyone["sections"][0]["rows"]) == 2


def test_csv_does_not_run_formulas(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra5@example.com")
    signup(client, session, "organisation", "ro4@example.com", org_name="=HYPERLINK(1)")
    csv = client.get(f"{REPORTS}/vouching_summary?format=csv", headers=admin.headers)
    assert "'=HYPERLINK(1)" in csv.text
    assert ",=HYPERLINK" not in csv.text


def test_run_store_list_and_download(
    client: TestClient, session: Session, reports_dir: Path
) -> None:
    admin = signup(client, session, "admin", "ra6@example.com")
    host = signup(client, session, "workhost", "rh1@example.com")
    body = {"date_from": "2026-10-20", "date_to": "2026-10-21"}
    url = f"{REPORTS}/users_registered_daily/run"

    assert client.post(url, json=body, headers=host.headers).status_code == 403
    created = client.post(url, json=body, headers=admin.headers)
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "succeeded"
    assert run["has_files"] is True
    repeated = client.post(url, json=body, headers=admin.headers)
    assert repeated.status_code == 200  # nothing ran again
    assert repeated.json()["id"] == run["id"]

    runs_url = f"{REPORTS}/runs?report_name=users_registered_daily"
    listing = client.get(runs_url, headers=admin.headers)
    assert listing.json()["total"] == 1
    assert client.get(f"{REPORTS}/runs", headers=host.headers).status_code == 403

    csv = client.get(f"{REPORTS}/runs/{run['id']}/download", headers=admin.headers)
    assert csv.status_code == 200
    assert "New users by type" in csv.text
    html = client.get(f"{REPORTS}/runs/{run['id']}/download?format=html", headers=admin.headers)
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<table>" in html.text

    backwards = {"date_from": "2026-10-21", "date_to": "2026-10-20"}
    bad = client.post(url, json=backwards, headers=admin.headers)
    assert bad.status_code == 422
    assert client.post(f"{REPORTS}/nope/run", json=body, headers=admin.headers).status_code == 404


def test_download_cannot_leave_the_output_folder(
    client: TestClient, session: Session, reports_dir: Path
) -> None:
    admin = signup(client, session, "admin", "ra7@example.com")
    body = {"date_from": "2026-10-20", "date_to": "2026-10-20"}
    run = client.post(f"{REPORTS}/active_users/run", json=body, headers=admin.headers).json()
    row = session.get(ReportRun, run["id"])
    assert row is not None
    row.file_path = "../../../../etc/passwd"
    session.commit()
    response = client.get(f"{REPORTS}/runs/{run['id']}/download", headers=admin.headers)
    assert response.status_code == 404


def test_download_needs_a_finished_run(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra8@example.com")
    missing = f"{REPORTS}/runs/00000000-0000-4000-8000-000000000000/download"
    assert client.get(missing, headers=admin.headers).status_code == 404


def test_schedules_can_be_listed_and_changed(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "ra9@example.com")
    host = signup(client, session, "workhost", "rh2@example.com")
    schedules = client.get(f"{REPORTS}/schedules", headers=admin.headers).json()
    assert {s["report_name"] for s in schedules} == {
        "users_registered_daily",
        "weekly_summary",
        "monthly_summary",
    }
    daily = next(s for s in schedules if s["report_name"] == "users_registered_daily")
    assert (daily["cron_expression"], daily["timezone"]) == ("5 0 * * *", "Asia/Dubai")

    url = f"{REPORTS}/schedules/users_registered_daily"
    change = {"cron_expression": "30 1 * * *", "timezone": "Asia/Dubai", "is_enabled": False}
    assert client.put(url, json=change, headers=host.headers).status_code == 403
    updated = client.put(url, json=change, headers=admin.headers)
    assert updated.status_code == 200
    assert updated.json()["is_enabled"] is False

    for bad in (
        {**change, "cron_expression": "every day please"},
        {**change, "cron_expression": "99 99 * * *"},
        {**change, "timezone": "Mars/Base"},
    ):
        assert client.put(url, json=bad, headers=admin.headers).status_code == 422
    unknown = f"{REPORTS}/schedules/not_a_report"
    assert client.put(unknown, json=change, headers=admin.headers).status_code == 404
