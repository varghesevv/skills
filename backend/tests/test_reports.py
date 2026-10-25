"""Report queries, files, idempotent runs and the scheduler jobs."""

import dataclasses
import secrets
import uuid
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import LoginHistory
from app.models.availability import FreelancerUnavailability
from app.models.ratings import UserRating
from app.models.reports import ReportRun, ReportSchedule
from app.models.reveals import PhoneReveal
from app.models.users import Freelancer, Organisation, WorkHost
from app.models.vouching import OrgFreelancer
from app.reports.definitions import REGISTRY
from app.reports.render import to_csv
from app.reports.runner import build_report, run_report, run_with_retry
from app.reports.types import ReportParams, ReportResult, Section
from app.reports.windows import window_from_dates
from app.services.accounts import create_account
from app.worker.jobs import catch_up, sync_jobs
from tests.test_search_api import freelancer

DUBAI = "Asia/Dubai"


def dubai(day: int, hour: int, minute: int = 0) -> datetime:
    """A time on the given day of October 2026 in Dubai (UTC+4), as UTC."""
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC) - timedelta(hours=4)


def params(first: date, last: date, **filters: object) -> ReportParams:
    start, end = window_from_dates(first, last, DUBAI)
    return ReportParams(start=start, end=end, timezone=DUBAI, **filters)  # type: ignore[arg-type]


def rows_of(session: Session, name: str, p: ReportParams, index: int = 0) -> list[list[object]]:
    return build_report(session, name, p).sections[index].rows  # type: ignore[return-value]


def set_created(session: Session, model: type, account_id: uuid.UUID, when: datetime) -> None:
    session.execute(update(model).where(model.id == account_id).values(created_at=when))
    session.commit()


def make_host(session: Session, email: str) -> WorkHost:
    account = create_account(
        session,
        "workhost",
        email=email,
        mobile_number="+971500000002",
        password=secrets.token_urlsafe(16),
    )
    assert isinstance(account, WorkHost)
    return account


def make_org(session: Session, email: str, name: str, *, approved: bool = True) -> Organisation:
    account = create_account(
        session,
        "organisation",
        email=email,
        mobile_number="+971500000003",
        password=secrets.token_urlsafe(16),
        org_name=name,
    )
    assert isinstance(account, Organisation)
    if approved:
        account.approval_status = "approved"
        session.commit()
    return account


# ---- the reports --------------------------------------------------------------------------


def test_registrations_per_day_counts_days_in_dubai_time(session: Session) -> None:
    f1, f2, f3, f_out = (freelancer(session, f"r{i}@example.com") for i in range(4))
    host = make_host(session, "rh@example.com")
    set_created(session, Freelancer, f1.id, dubai(20, 10))
    set_created(session, Freelancer, f2.id, dubai(20, 23, 30))
    set_created(session, Freelancer, f3.id, dubai(21, 0, 30))  # still the 20th in UTC
    set_created(session, Freelancer, f_out.id, dubai(22, 1))
    set_created(session, WorkHost, host.id, dubai(20, 12))

    rows = rows_of(session, "registrations_per_day", params(date(2026, 10, 20), date(2026, 10, 21)))
    assert rows == [
        ["2026-10-20", "freelancer", 2],
        ["2026-10-20", "workhost", 1],
        ["2026-10-21", "freelancer", 1],
    ]


def test_users_registered_daily_lists_counts_and_people(session: Session) -> None:
    new = freelancer(session, "new.person@example.com")
    old = freelancer(session, "old.person@example.com")
    org = make_org(session, "neworg@example.com", "New Org")
    set_created(session, Freelancer, new.id, dubai(20, 9))
    set_created(session, Freelancer, old.id, dubai(15, 9))
    set_created(session, Organisation, org.id, dubai(20, 18))
    day = params(date(2026, 10, 20), date(2026, 10, 20))
    counts, people = build_report(session, "users_registered_daily", day).sections
    assert counts.rows == [["freelancer", 1], ["workhost", 0], ["organisation", 1]]
    assert [(row[0], row[2]) for row in people.rows] == [
        ("freelancer", "new.person@example.com"),
        ("organisation", "neworg@example.com"),
    ]


def test_active_users_counts_logins(session: Session) -> None:
    active = freelancer(session, "act@example.com")
    idle = make_host(session, "idle@example.com")
    session.execute(
        update(Freelancer).where(Freelancer.id == active.id).values(last_login_at=dubai(20, 9))
    )
    session.execute(
        update(WorkHost).where(WorkHost.id == idle.id).values(last_login_at=dubai(1, 9))
    )
    for when, ok in ((dubai(20, 9), True), (dubai(20, 10), True), (dubai(20, 11), False)):
        session.add(
            LoginHistory(
                user_type="freelancer",
                user_id=active.id,
                login_email="act@example.com",
                succeeded=ok,
                login_time=when,
            )
        )
    session.add(
        LoginHistory(
            user_type="freelancer",
            login_email="act@example.com",
            succeeded=False,
            login_time=dubai(1, 9),  # outside the window
        )
    )
    session.commit()
    day = params(date(2026, 10, 20), date(2026, 10, 20))
    rows = {row[0]: row[1:] for row in rows_of(session, "active_users", day)}
    assert rows["freelancer"] == [1, 2, 1]
    assert rows["workhost"] == [0, 0, 0]
    workhosts_only = params(date(2026, 10, 20), date(2026, 10, 20), user_type="workhost")
    only = rows_of(session, "active_users", workhosts_only)
    assert [row[0] for row in only] == ["workhost"]


def test_freelancers_by_label(session: Session) -> None:
    freelancer(session, "l1@example.com", labels=(("language", "English"),))
    freelancer(session, "l2@example.com", skills=(("plumbing", "basic"), ("electrical", None)))
    rows = rows_of(session, "freelancers_by_label", params(date(2026, 10, 1), date(2026, 10, 2)))
    by_label = {(row[0], row[1]): row[2] for row in rows}
    assert by_label[("skill", "plumbing")] == 2
    assert by_label[("skill", "electrical")] == 1
    assert by_label[("language", "English")] == 1
    assert by_label[("language", "Tamil")] == 0
    assert not any(row[0] == "skill_level" for row in rows)


def test_top_rated_and_rating_per_skill(session: Session) -> None:
    best = freelancer(session, "tb@example.com")
    other = freelancer(session, "to@example.com")
    host_a, host_b = make_host(session, "tha@example.com"), make_host(session, "thb@example.com")
    now = datetime.now(UTC)
    for host, target, rating in ((host_a, best, 8), (host_b, best, 10), (host_a, other, 6)):
        session.add(
            UserRating(work_host_id=host.id, freelancer_id=target.id, rating=rating, rated_on=now)
        )
    session.commit()
    window = ReportParams(
        start=now - timedelta(days=1), end=now + timedelta(days=1), timezone=DUBAI
    )
    top, per_skill = build_report(session, "top_rated", window).sections
    assert [row[0] for row in top.rows] == [str(best.id), str(other.id)]
    assert top.rows[0][1:] == [9.0, 2]
    assert per_skill.rows == [["plumbing", 8.0, 3, 2]]

    strict = dataclasses.replace(window, min_ratings=2)
    assert [row[0] for row in build_report(session, "top_rated", strict).sections[0].rows] == [
        str(best.id)
    ]


def test_vouching_summary_and_organisation_scope(session: Session) -> None:
    alpha = make_org(session, "alpha@example.com", "Alpha Org")
    make_org(session, "beta@example.com", "Beta Org")
    make_org(session, "gamma@example.com", "Gamma Org", approved=False)
    people = [freelancer(session, f"vs{i}@example.com") for i in range(3)]
    session.add_all(
        [
            OrgFreelancer(org_id=alpha.id, freelancer_id=people[0].id, status="approved"),
            OrgFreelancer(org_id=alpha.id, freelancer_id=people[1].id, status="pending"),
            OrgFreelancer(
                org_id=alpha.id, freelancer_id=people[2].id, status="revoked", is_active=False
            ),
        ]
    )
    session.commit()
    window = params(date(2026, 10, 1), date(2026, 10, 2))
    rows = rows_of(session, "vouching_summary", window)
    assert [(row[1], *row[2:]) for row in rows] == [
        ("Alpha Org", 3, 1, 1, 1),
        ("Beta Org", 0, 0, 0, 0),
    ]
    scoped = rows_of(session, "vouching_summary", dataclasses.replace(window, org_id=alpha.id))
    assert [row[1] for row in scoped] == ["Alpha Org"]


def test_rate_distribution_filters(session: Session) -> None:
    freelancer(session, "d1@example.com", rate=20)
    freelancer(session, "d2@example.com", rate=40)
    freelancer(session, "d3@example.com", rate=30, currency="USD", skills=(("electrical", None),))
    window = params(date(2026, 10, 1), date(2026, 10, 2))
    assert rows_of(session, "rate_distribution", window) == [
        ["electrical", "USD", 1, 30.0, 30.0, 30.0],
        ["plumbing", "AED", 2, 30.0, 20.0, 40.0],
    ]
    by_skill = dataclasses.replace(window, skill="PLUMBING")
    only_skill = rows_of(session, "rate_distribution", by_skill)
    assert [row[0] for row in only_skill] == ["plumbing"]
    only_usd = rows_of(session, "rate_distribution", dataclasses.replace(window, currency="usd"))
    assert [row[1] for row in only_usd] == ["USD"]


def test_availability_overview(session: Session) -> None:
    busy = freelancer(session, "av1@example.com")
    freelancer(session, "av2@example.com")
    freelancer(session, "av3@example.com", rate=None)  # not searchable, not counted
    session.add(
        FreelancerUnavailability(
            freelancer_id=busy.id, unavailable_from=dubai(21, 10), unavailable_to=dubai(21, 12)
        )
    )
    session.commit()
    rows = rows_of(session, "availability_overview", params(date(2026, 10, 20), date(2026, 10, 22)))
    assert rows == [
        ["2026-10-20", 2, 0, 2],
        ["2026-10-21", 2, 1, 1],
        ["2026-10-22", 2, 0, 2],
    ]


def test_availability_overview_limits_the_range(session: Session) -> None:
    from app.reports.types import ReportError

    with pytest.raises(ReportError):
        build_report(session, "availability_overview", params(date(2026, 1, 1), date(2026, 6, 1)))


def test_phone_reveals_report(session: Session) -> None:
    plumber = freelancer(session, "pr1@example.com", skills=(("plumbing", None),))
    cook = freelancer(session, "pr2@example.com", skills=(("cooking", None),))
    host = make_host(session, "prh1@example.com")
    other = make_host(session, "prh2@example.com")
    inside = dubai(10, 12)

    def reveal(
        who: WorkHost, target: Freelancer, channel: str, source: str, skills: list[str]
    ) -> None:
        session.add(
            PhoneReveal(
                work_host_id=who.id,
                freelancer_id=target.id,
                revealed_at=inside,
                channel=channel,
                source=source,
                searched_skills=skills or None,
            )
        )

    reveal(host, plumber, "dial", "search", ["plumbing", "cleaning"])
    reveal(host, plumber, "show", "detail", [])  # the same pair again
    reveal(host, cook, "show", "search", ["plumbing"])
    reveal(other, plumber, "show", "search", [])
    session.add(  # outside the window: ignored
        PhoneReveal(
            work_host_id=other.id,
            freelancer_id=cook.id,
            revealed_at=dubai(20, 12),
            channel="show",
            source="search",
        )
    )
    rating = UserRating(
        work_host_id=host.id, freelancer_id=plumber.id, rating=8, rated_on=dubai(11, 9)
    )
    session.add(rating)
    session.commit()

    window = params(date(2026, 10, 10), date(2026, 10, 12))
    sections = build_report(session, "phone_reveals", window).sections
    summary = dict(sections[0].rows)
    assert summary["reveals"] == 4
    assert summary["work_hosts"] == 2
    assert summary["freelancers_revealed"] == 2
    assert summary["reveals_on_phone_dialler"] == 1
    assert summary["reveals_from_search_page"] == 3
    assert summary["host_freelancer_pairs"] == 3
    assert summary["pairs_rated_afterwards"] == 1
    assert summary["rated_afterwards_percent"] == 33.3
    assert sections[2].rows[0][2:4] == [3, 2]  # the busiest work host
    assert sections[3].rows == [["plumbing", 3, 1], ["cooking", 1, 1]]
    assert sections[4].rows == [["plumbing", 2], ["cleaning", 1]]
    assert sections[5].rows[0][2:] == [3, 2]


def test_phone_reveals_report_when_empty(session: Session) -> None:
    window = params(date(2026, 10, 10), date(2026, 10, 12))
    sections = build_report(session, "phone_reveals", window).sections
    assert dict(sections[0].rows)["reveals"] == 0
    assert dict(sections[0].rows)["rated_afterwards_percent"] == 0
    assert all(section.rows == [] for section in sections[1:])


def test_monthly_summary_runs_every_report(session: Session) -> None:
    freelancer(session, "m1@example.com")
    sections = build_report(
        session, "monthly_summary", params(date(2026, 10, 1), date(2026, 10, 31))
    ).sections
    assert len(sections) == 14  # RP-01 to RP-08: RP-04 gives two sections, RP-08 gives six


# ---- output files ------------------------------------------------------------------------


def test_csv_neutralises_spreadsheet_formulas() -> None:
    rows = [['=HYPERLINK("x")', 1], ["-2+3", 2]]
    result = ReportResult([Section("Names", ["name", "n"], rows)])
    text = to_csv(result)
    assert "'=HYPERLINK" in text
    assert "\n=HYPERLINK" not in text
    assert "'-2+3" in text


def test_csv_with_several_sections_has_titles() -> None:
    result = ReportResult([Section("A", ["x"], [[1]]), Section("B", ["y"], [[2]])])
    assert to_csv(result) == "A\nx\n1\n\nB\ny\n2\n"


# ---- running reports ----------------------------------------------------------------------


def test_run_writes_files_and_is_idempotent(session: Session, tmp_path: Path) -> None:
    freelancer(session, "run1@example.com")
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    run, executed = run_report(
        session, "users_registered_daily", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert executed
    assert run.status == "succeeded"
    assert run.row_count is not None
    assert run.file_path is not None
    csv_file = tmp_path / run.file_path
    assert csv_file.is_file()
    assert csv_file.with_suffix(".html").is_file()
    assert "New users by type" in csv_file.read_text()

    again, executed_again = run_report(
        session, "users_registered_daily", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert not executed_again
    assert again.id == run.id
    assert len(session.scalars(select(ReportRun)).all()) == 1


def test_failed_run_is_recorded_and_retried(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    original = REGISTRY["users_registered_daily"]

    def explode(*_: object) -> list[Section]:
        raise RuntimeError("boom")

    monkeypatch.setitem(REGISTRY, original.name, dataclasses.replace(original, build=explode))
    failed, _ = run_report(session, original.name, start, end, output_dir=tmp_path, timezone=DUBAI)
    assert failed.status == "failed"
    assert failed.error_message == "RuntimeError: boom"
    assert failed.file_path is None

    monkeypatch.setitem(REGISTRY, original.name, original)
    fixed, executed = run_report(
        session, original.name, start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert executed
    assert fixed.id == failed.id
    assert fixed.status == "succeeded"
    assert fixed.error_message is None


def test_run_with_retry_tries_a_second_time(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    original = REGISTRY["users_registered_daily"]
    calls: list[int] = []

    def flaky(db: Session, p: ReportParams) -> list[Section]:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first attempt fails")
        return original.build(db, p)

    monkeypatch.setitem(REGISTRY, original.name, dataclasses.replace(original, build=flaky))
    status = run_with_retry(
        lambda: nullcontext(session),
        original.name,
        start,
        end,
        output_dir=tmp_path,
        timezone=DUBAI,
        wait_seconds=0,
    )
    assert status == "succeeded"
    assert len(calls) == 2


def test_stale_running_run_is_taken_over(session: Session, tmp_path: Path) -> None:
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    stale = ReportRun(
        report_name="users_registered_daily",
        window_from=start,
        window_to=end,
        status="running",
        started_at=datetime.now(UTC) - timedelta(hours=3),
    )
    fresh = ReportRun(
        report_name="active_users",
        window_from=start,
        window_to=end,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add_all([stale, fresh])
    session.commit()
    taken, executed = run_report(
        session, "users_registered_daily", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert executed
    assert taken.status == "succeeded"
    untouched, executed = run_report(
        session, "active_users", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert not executed
    assert untouched.status == "running"


# ---- the worker's jobs ---------------------------------------------------------------------


def test_sync_jobs_follows_the_schedules_table(session: Session) -> None:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.start(paused=True)  # running like the worker's scheduler, but nothing fires
    try:
        check_sync_jobs(scheduler, session)
    finally:
        scheduler.shutdown(wait=False)


def check_sync_jobs(scheduler: BackgroundScheduler, session: Session) -> None:
    settings = get_settings()

    def factory() -> nullcontext[Session]:
        return nullcontext(session)

    names = sync_jobs(scheduler, factory, settings)
    assert names == ["monthly_summary", "users_registered_daily", "weekly_summary"]
    assert {job.id for job in scheduler.get_jobs()} == set(names)

    daily = session.scalar(
        select(ReportSchedule).where(ReportSchedule.report_name == "users_registered_daily")
    )
    weekly = session.scalar(
        select(ReportSchedule).where(ReportSchedule.report_name == "weekly_summary")
    )
    assert daily is not None
    assert weekly is not None
    daily.cron_expression = "30 1 * * *"
    weekly.is_enabled = False
    session.commit()
    sync_jobs(scheduler, factory, settings)
    assert {job.id for job in scheduler.get_jobs()} == {"monthly_summary", "users_registered_daily"}
    changed = scheduler.get_job("users_registered_daily")
    assert changed is not None
    assert changed.name.startswith("30 1 * * *|")

    daily.cron_expression = "not a cron"
    session.commit()
    sync_jobs(scheduler, factory, settings)  # an invalid schedule must not crash the worker
    assert {job.id for job in scheduler.get_jobs()} == {"monthly_summary", "users_registered_daily"}


def test_catch_up_runs_missed_windows_once(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        settings = get_settings()

        def factory() -> nullcontext[Session]:
            return nullcontext(session)

        catch_up(factory, settings)
        runs = session.scalars(select(ReportRun)).all()
        assert sorted(run.report_name for run in runs) == [
            "monthly_summary",
            "users_registered_daily",
            "weekly_summary",
        ]
        assert all(run.status == "succeeded" for run in runs)
        catch_up(factory, settings)
        assert len(session.scalars(select(ReportRun)).all()) == 3
    finally:
        get_settings.cache_clear()
