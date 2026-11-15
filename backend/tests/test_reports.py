"""Report queries over people, files, idempotent runs and the scheduler jobs."""

import dataclasses
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    MoveRequest,
    Person,
    PersonLabel,
    PersonPhoneReveal,
    PersonUnavailability,
    Rating,
    StatusChange,
    Vouch,
)
from app.models.auth import LoginHistory
from app.models.labels import Label
from app.models.reports import ReportRun, ReportSchedule
from app.reports.definitions import REGISTRY
from app.reports.render import to_csv
from app.reports.runner import build_report, run_report, run_with_retry
from app.reports.types import ReportError, ReportParams, ReportResult, Section
from app.reports.windows import window_from_dates
from app.worker.jobs import catch_up, sync_jobs
from tests.test_person_auth import Member, add_member
from tests.test_search_api import provider
from tests.trust_helpers import World, make_person

pytestmark = pytest.mark.db

DUBAI = "Asia/Dubai"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def dubai(day: int, hour: int, minute: int = 0) -> datetime:
    """A time on the given day of October 2026 in Dubai (UTC+4), as UTC."""
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC) - timedelta(hours=4)


def params(first: date, last: date, **filters: object) -> ReportParams:
    start, end = window_from_dates(first, last, DUBAI)
    return ReportParams(start=start, end=end, timezone=DUBAI, **filters)  # type: ignore[arg-type]


def rows_of(session: Session, name: str, p: ReportParams, index: int = 0) -> list[list[object]]:
    return build_report(session, name, p).sections[index].rows  # type: ignore[return-value]


def set_created(session: Session, person: Person, when: datetime) -> None:
    session.execute(update(Person).where(Person.id == person.id).values(created_at=when))
    session.flush()


def code(person: Person) -> str:
    return str(person.id)[:8]


# ---- the reports --------------------------------------------------------------------------


def test_registrations_per_day_counts_days_in_dubai_time(world: World) -> None:
    session = world.session
    one, two, three, outside = (
        add_member(world, "searcher"),
        add_member(world, "pending"),
        add_member(world, "provider"),
        add_member(world, "searcher"),
    )
    set_created(session, one.person, dubai(20, 10))
    set_created(session, two.person, dubai(20, 23, 30))
    set_created(session, three.person, dubai(21, 0, 30))  # still the 20th in UTC
    set_created(session, outside.person, dubai(22, 1))
    rows = rows_of(session, "registrations_per_day", params(date(2026, 10, 20), date(2026, 10, 21)))
    name = world.church.name
    assert rows == [
        ["2026-10-20", name, "pending", 1],
        ["2026-10-20", name, "searcher", 1],
        ["2026-10-21", name, "provider", 1],
    ]


def test_a_report_can_be_limited_to_one_church(world: World) -> None:
    session = world.session
    other_church, other_group, _ = world.add_church("Hope Church")
    here = add_member(world, "searcher")
    there = make_person(other_church, other_group, "searcher")
    session.add(there)
    session.flush()
    set_created(session, here.person, dubai(20, 10))
    set_created(session, there, dubai(20, 11))
    window = params(date(2026, 10, 20), date(2026, 10, 20))
    both = rows_of(session, "registrations_per_day", window)
    assert {row[1] for row in both} == {world.church.name, "Hope Church"}
    only = rows_of(
        session,
        "registrations_per_day",
        params(date(2026, 10, 20), date(2026, 10, 20), church_id=other_church.id),
    )
    assert [row[1] for row in only] == ["Hope Church"]


def test_signups_daily_counts_new_applicants_by_what_they_asked_for(world: World) -> None:
    session = world.session
    for requested in ("searcher", "provider", "provider"):
        member = add_member(world, "pending", requested_status=requested)
        set_created(session, member.person, dubai(20, 9))
    old = add_member(world, "pending", requested_status="searcher")
    set_created(session, old.person, dubai(15, 9))
    sections = build_report(
        session, "signups_daily", params(date(2026, 10, 20), date(2026, 10, 20))
    ).sections
    name = world.church.name
    assert sections[0].rows == [[name, "provider", 2], [name, "searcher", 1]]
    assert sections[1].rows == [["new_applicants", 3]]


def test_active_people_and_logins_by_status(world: World) -> None:
    session = world.session
    active = add_member(world, "searcher")
    idle = add_member(world, "provider")
    session.execute(
        update(Person).where(Person.id == active.person.id).values(last_login_at=dubai(20, 9))
    )
    session.execute(
        update(Person).where(Person.id == idle.person.id).values(last_login_at=dubai(1, 9))
    )
    for when, ok in ((dubai(20, 9), True), (dubai(20, 10), True), (dubai(20, 11), False)):
        session.add(
            LoginHistory(
                user_type="person",
                user_id=active.person.id,
                login_email="act@example.com",
                succeeded=ok,
                login_time=when,
            )
        )
    session.add_all(
        [
            LoginHistory(  # an address nobody has
                user_type="person",
                login_email="nobody@example.com",
                succeeded=False,
                login_time=dubai(20, 12),
            ),
            LoginHistory(  # outside the window
                user_type="person",
                user_id=active.person.id,
                login_email="act@example.com",
                succeeded=False,
                login_time=dubai(1, 9),
            ),
        ]
    )
    session.flush()
    day = params(date(2026, 10, 20), date(2026, 10, 20))
    rows = {row[0]: row[1:] for row in rows_of(session, "active_users", day)}
    assert rows["searcher"] == [1, 2, 1]
    assert rows["provider"] == [0, 0, 0]
    assert rows["unknown address"] == [0, 0, 1]
    only = rows_of(
        session, "active_users", params(date(2026, 10, 20), date(2026, 10, 20), status="provider")
    )
    assert [row[0] for row in only] == ["provider"]


def test_providers_by_label_counts_only_open_providers(world: World) -> None:
    session = world.session
    provider(world, labels=(("language", "English"),))
    provider(world, skills=(("plumbing", "basic"), ("electrical", None)))
    provider(world, status="searcher")  # not a provider
    closed = provider(world)
    closed.person.closed_at = datetime.now(UTC)
    closed.person.home_group_id = None
    closed.person.full_name = closed.person.email = closed.person.mobile_number = None
    closed.person.password_hash = None
    session.flush()
    rows = rows_of(session, "providers_by_label", params(date(2026, 10, 1), date(2026, 10, 2)))
    by_label = {(row[0], row[1]): row[2] for row in rows}
    assert by_label[("skill", "plumbing")] == 2
    assert by_label[("skill", "electrical")] == 1
    assert by_label[("language", "English")] == 1
    assert by_label[("language", "Tamil")] == 0
    assert not any(row[0] == "skill_level" for row in rows)


def test_top_rated_and_rating_per_skill_show_codes_not_names(world: World) -> None:
    session = world.session
    best, other = provider(world), provider(world, skills=(("plumbing", None),))
    raters = [add_member(world, "searcher") for _ in range(2)]
    now = datetime.now(UTC)
    for rater, target, rating in (
        (raters[0], best, 8),
        (raters[1], best, 10),
        (raters[0], other, 6),
    ):
        session.add(
            Rating(
                rater_id=rater.person.id, provider_id=target.person.id, rating=rating, rated_on=now
            )
        )
    session.flush()
    window = ReportParams(
        start=now - timedelta(days=1), end=now + timedelta(days=1), timezone=DUBAI
    )
    top, per_skill = build_report(session, "top_rated", window).sections
    assert [row[0] for row in top.rows] == [code(best.person), code(other.person)]
    assert top.rows[0][1:] == [9.0, 2]
    assert per_skill.rows == [["plumbing", 8.0, 3, 2]]
    assert str(best.person.full_name) not in str(top.rows)

    strict = dataclasses.replace(window, min_ratings=2)
    assert [row[0] for row in build_report(session, "top_rated", strict).sections[0].rows] == [
        code(best.person)
    ]


def test_verification_summary_counts_people_admissions_and_declines(world: World) -> None:
    session = world.session
    group = world.group
    searcher = add_member(world, "pending")
    add_member(world, "provider")
    add_member(world, "pending")
    gone = add_member(world, "provider")
    gone.person.status = "revoked"
    gone.person.last_home_group_id = group.id
    gone.person.home_group_id = None
    declined = add_member(world, "pending")
    declined.person.closed_at = dubai(20, 12)
    declined.person.home_group_id = None
    declined.person.full_name = declined.person.email = declined.person.mobile_number = None
    declined.person.password_hash = None
    # An admission on the 20th, five days after the sign-up, with two vouches (given while the
    # applicant was still pending: the database accepts a vouch for no one else).
    voucher_one, voucher_two = add_member(world, "provider"), add_member(world, "provider")
    session.add_all(
        [
            Vouch(applicant_id=searcher.person.id, voucher_id=voucher_one.person.id),
            Vouch(applicant_id=searcher.person.id, voucher_id=voucher_two.person.id),
            StatusChange(
                person_id=searcher.person.id,
                from_status=None,
                to_status="pending",
                kind="signup",
                at=dubai(15, 9),
            ),
        ]
    )
    session.flush()
    searcher.person.status = "searcher"
    session.add(
        StatusChange(
            person_id=searcher.person.id,
            from_status="pending",
            to_status="searcher",
            changed_by_id=world.owner.id,
            kind="admit",
            at=dubai(20, 9),
        )
    )
    session.flush()
    sections = build_report(
        session, "verification_summary", params(date(2026, 10, 20), date(2026, 10, 20))
    ).sections
    people = {(row[0], row[1]): row[2:] for row in sections[0].rows}
    # pending, searchers, providers, leaders, revoked (the closed person is not counted)
    assert people[(world.church.name, group.name)] == [1, 1, 3, 1, 1]
    period = sections[1].rows
    assert period == [[world.church.name, 1, 1, 5.0, 2.0]]


def test_rate_distribution_filters(world: World) -> None:
    provider(world, rate=20)
    provider(world, rate=40)
    provider(world, rate=30, currency="USD", skills=(("electrical", None),))
    provider(world, status="searcher", rate=999)  # not a provider
    window = params(date(2026, 10, 1), date(2026, 10, 2))
    rows = rows_of(world.session, "rate_distribution", window)
    assert rows == [
        ["electrical", "USD", 1, 30.0, 30.0, 30.0],
        ["plumbing", "AED", 2, 30.0, 20.0, 40.0],
    ]
    only_aed = params(date(2026, 10, 1), date(2026, 10, 2), currency="aed")
    assert [row[0] for row in rows_of(world.session, "rate_distribution", only_aed)] == ["plumbing"]
    only_skill = params(date(2026, 10, 1), date(2026, 10, 2), skill="ELECTRICAL")
    assert [row[0] for row in rows_of(world.session, "rate_distribution", only_skill)] == [
        "electrical"
    ]


def test_availability_overview(world: World) -> None:
    session = world.session
    busy = provider(world)
    provider(world)
    provider(world, skills=())  # no skill: not searchable, not counted
    session.add(
        PersonUnavailability(
            person_id=busy.person.id, unavailable_from=dubai(21, 10), unavailable_to=dubai(21, 12)
        )
    )
    session.flush()
    rows = rows_of(session, "availability_overview", params(date(2026, 10, 20), date(2026, 10, 22)))
    assert rows == [
        ["2026-10-20", 2, 0, 2],
        ["2026-10-21", 2, 1, 1],
        ["2026-10-22", 2, 0, 2],
    ]


def test_availability_overview_limits_the_range(session: Session) -> None:
    with pytest.raises(ReportError):
        build_report(session, "availability_overview", params(date(2026, 1, 1), date(2026, 6, 1)))


def test_phone_reveals_report(world: World) -> None:
    session = world.session
    plumber = provider(world, skills=(("plumbing", None),))
    cook = provider(world, skills=(("electrical", None),))
    one, other = add_member(world, "searcher"), add_member(world, "searcher")
    inside = dubai(10, 12)

    def reveal(who: Member, target: Member, channel: str, source: str, skills: list[str]) -> None:
        session.add(
            PersonPhoneReveal(
                revealer_id=who.person.id,
                provider_id=target.person.id,
                revealed_at=inside,
                channel=channel,
                source=source,
                searched_skills=skills or None,
            )
        )

    reveal(one, plumber, "dial", "search", ["plumbing", "networking"])
    reveal(one, plumber, "show", "detail", [])  # the same pair again
    reveal(one, cook, "show", "search", ["plumbing"])
    reveal(other, plumber, "show", "search", [])
    session.add(  # outside the window: ignored
        PersonPhoneReveal(
            revealer_id=other.person.id,
            provider_id=cook.person.id,
            revealed_at=dubai(20, 12),
            channel="show",
            source="search",
        )
    )
    session.add(
        Rating(
            rater_id=one.person.id, provider_id=plumber.person.id, rating=8, rated_on=dubai(11, 9)
        )
    )
    session.flush()

    sections = build_report(
        session, "phone_reveals", params(date(2026, 10, 10), date(2026, 10, 12))
    ).sections
    summary = dict(sections[0].rows)
    assert summary["reveals"] == 4
    assert summary["searchers"] == 2
    assert summary["providers_revealed"] == 2
    assert summary["reveals_on_phone_dialler"] == 1
    assert summary["reveals_from_search_page"] == 3
    assert summary["searcher_provider_pairs"] == 3
    assert summary["pairs_rated_afterwards"] == 1
    assert summary["rated_afterwards_percent"] == 33.3
    assert sections[2].rows[0][:1] == [code(one.person)]  # the busiest searcher, by code
    assert sections[2].rows[0][1:3] == [3, 2]
    assert sections[3].rows == [["plumbing", 3, 1], ["electrical", 1, 1]]
    assert sections[4].rows == [["plumbing", 2], ["networking", 1]]
    assert sections[5].rows[0][:1] == [code(plumber.person)]
    assert sections[5].rows[0][1:] == [3, 2]
    assert str(one.person.full_name) not in str(sections)


def test_phone_reveals_report_when_empty(session: Session) -> None:
    sections = build_report(
        session, "phone_reveals", params(date(2026, 10, 10), date(2026, 10, 12))
    ).sections
    assert dict(sections[0].rows)["reveals"] == 0
    assert dict(sections[0].rows)["rated_afterwards_percent"] == 0
    assert all(section.rows == [] for section in sections[1:])


def test_trust_events_count_what_happened_in_the_period(world: World) -> None:
    session = world.session
    member = add_member(world, "provider")
    flagged = add_member(world, "searcher", flagged_for_recheck=True)

    def change(kind: str, at: datetime, to: str = "revoked") -> None:
        session.add(
            StatusChange(
                person_id=member.person.id,
                from_status="provider",
                to_status=to,
                changed_by_id=world.owner.id,
                kind=kind,
                at=at,
            )
        )

    change("revoke", dubai(20, 9))
    change("revoke", dubai(20, 10))
    change("reinstate", dubai(21, 9), "provider")
    change("revoke", dubai(15, 9))  # outside the window
    other_church, other_group, _ = world.add_church("Hope Church")
    other_group.closed_at = dubai(20, 8)
    other_church.closed_at = dubai(20, 8)
    lead = add_member(world, "searcher")
    second_group = world.add_group(lead.person, "Second group")
    session.add(
        MoveRequest(
            person_id=member.person.id,
            from_group_id=world.group.id,
            to_group_id=second_group.id,
            created_at=dubai(19, 9),
            completed_at=dubai(20, 9),
        )
    )
    session.flush()
    sections = build_report(
        session, "trust_events", params(date(2026, 10, 20), date(2026, 10, 21))
    ).sections
    assert sections[0].rows == [
        [world.church.name, "reinstate", 1],
        [world.church.name, "revoke", 2],
    ]
    assert sections[1].rows == [[world.church.name, 1]]
    assert sections[2].rows == [["Hope Church", 1]]
    assert [row[0] for row in sections[3].rows] == ["Hope Church"]
    assert sections[4].rows == [[world.church.name, 1]]
    assert flagged.person.flagged_for_recheck is True
    # An ADMIN's church sees none of the other church's closures.
    mine = build_report(
        session,
        "trust_events",
        params(date(2026, 10, 20), date(2026, 10, 21), church_id=world.church.id),
    ).sections
    assert mine[2].rows == [] and mine[3].rows == []


def test_reports_limited_to_a_church_hold_only_that_church(world: World) -> None:
    session = world.session
    other_church, other_group, _ = world.add_church("Hope Church")

    def there(status: str) -> Person:
        person = make_person(other_church, other_group, status)
        session.add(person)
        session.flush()
        return person

    here_provider, there_provider = provider(world), there("provider")
    session.add(
        PersonLabel(
            person_id=there_provider.id,
            label_id=session.scalars(select(Label.id).where(Label.label_name == "plumbing")).one(),
        )
    )
    here_searcher, there_searcher = add_member(world, "searcher"), there("searcher")
    now = dubai(10, 12)
    session.execute(
        update(Person)
        .where(Person.id.in_([here_searcher.person.id, there_searcher.id]))
        .values(last_login_at=now)
    )
    for rater, target in (
        (here_searcher.person, here_provider.person),
        (there_searcher, there_provider),
    ):
        session.add(Rating(rater_id=rater.id, provider_id=target.id, rating=7, rated_on=now))
        session.add(
            PersonPhoneReveal(
                revealer_id=rater.id,
                provider_id=target.id,
                revealed_at=now,
                channel="show",
                source="detail",
            )
        )
        session.add(
            LoginHistory(
                user_type="person",
                user_id=rater.id,
                login_email="x@example.com",
                succeeded=True,
                login_time=now,
            )
        )
    session.add(
        LoginHistory(
            user_type="person", login_email="nobody@example.com", succeeded=False, login_time=now
        )
    )
    # A failed attempt of an account of the older kind (rows that stay until the table is
    # reshaped) is not a person's and is not counted.
    session.add(
        LoginHistory(
            user_type="workhost", login_email="older@example.com", succeeded=False, login_time=now
        )
    )
    session.flush()
    window = params(date(2026, 10, 10), date(2026, 10, 10))
    limited = params(date(2026, 10, 10), date(2026, 10, 10), church_id=other_church.id)

    both = build_report(session, "top_rated", window).sections[0].rows
    assert {row[0] for row in both} == {code(here_provider.person), code(there_provider)}
    only = build_report(session, "top_rated", limited).sections[0].rows
    assert [row[0] for row in only] == [code(there_provider)]
    per_skill = build_report(session, "top_rated", limited).sections[1].rows
    assert per_skill == [["plumbing", 7.0, 1, 1]]

    everyone = build_report(session, "phone_reveals", window).sections
    assert dict(everyone[0].rows)["reveals"] == 2
    mine = build_report(session, "phone_reveals", limited).sections
    assert dict(mine[0].rows)["reveals"] == 1
    assert [row[0] for row in mine[5].rows] == [code(there_provider)]
    assert [row[0] for row in mine[2].rows] == [code(there_searcher)]

    all_rows = {row[0]: row[1:] for row in rows_of(session, "active_users", window)}
    assert all_rows["searcher"] == [2, 2, 0]
    assert all_rows["unknown address"] == [0, 0, 1]
    church_rows = {row[0]: row[1:] for row in rows_of(session, "active_users", limited)}
    assert church_rows["searcher"] == [1, 1, 0]
    assert "unknown address" not in church_rows  # a failed attempt belongs to no church


def test_monthly_summary_runs_every_report(world: World) -> None:
    provider(world)
    sections = build_report(
        world.session, "monthly_summary", params(date(2026, 10, 1), date(2026, 10, 31))
    ).sections
    # RP-01 to RP-09: RP-04 gives two sections, RP-05 two, RP-08 six and RP-09 five.
    assert len(sections) == 20


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
    World(session)  # a church with its OWNER, so there is something to count
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    run, executed = run_report(
        session, "signups_daily", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert executed
    assert run.status == "succeeded"
    assert run.row_count is not None
    assert run.file_path is not None
    csv_file = tmp_path / run.file_path
    assert csv_file.is_file()
    assert csv_file.with_suffix(".html").is_file()
    assert "New applicants by church and requested status" in csv_file.read_text()

    again, executed_again = run_report(
        session, "signups_daily", start, end, output_dir=tmp_path, timezone=DUBAI
    )
    assert not executed_again
    assert again.id == run.id
    assert len(session.scalars(select(ReportRun)).all()) == 1


def test_failed_run_is_recorded_and_retried(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 20), DUBAI)
    original = REGISTRY["signups_daily"]

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
    original = REGISTRY["signups_daily"]
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
        report_name="signups_daily",
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
        session, "signups_daily", start, end, output_dir=tmp_path, timezone=DUBAI
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
    assert names == ["monthly_summary", "signups_daily", "weekly_summary"]
    assert {job.id for job in scheduler.get_jobs()} == set(names)

    daily = session.scalar(
        select(ReportSchedule).where(ReportSchedule.report_name == "signups_daily")
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
    assert {job.id for job in scheduler.get_jobs()} == {"monthly_summary", "signups_daily"}
    changed = scheduler.get_job("signups_daily")
    assert changed is not None
    assert changed.name.startswith("30 1 * * *|")

    daily.cron_expression = "not a cron"
    session.commit()
    sync_jobs(scheduler, factory, settings)  # an invalid schedule must not crash the worker
    assert {job.id for job in scheduler.get_jobs()} == {"monthly_summary", "signups_daily"}


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
            "signups_daily",
            "weekly_summary",
        ]
        assert all(run.status == "succeeded" for run in runs)
        catch_up(factory, settings)
        assert len(session.scalars(select(ReportRun)).all()) == 3
    finally:
        get_settings.cache_clear()
