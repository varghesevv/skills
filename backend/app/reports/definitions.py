"""The report queries. Each returns sections (a title, columns and rows).

Reports hold aggregates. The few rows about one person show a short reference code (the first
8 characters of the id), never a name, an email or a mobile number. Every query counts only the
people it is about and limits itself to `p.church_id` when that is set (an ADMIN's reports
always are).
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    ColumnElement,
    Date,
    String,
    and_,
    cast,
    exists,
    func,
    select,
    text,
    true,
)
from sqlalchemy.orm import Session, aliased

from app.models.auth import LoginHistory
from app.models.chat import ChatReport
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK
from app.models.labels import Label, PersonLabel
from app.models.ratings import Rating
from app.models.reveals import PhoneReveal
from app.models.trust import MoveRequest, StatusChange, Vouch
from app.reports.types import ReportDef, ReportError, ReportParams, Section, cell

MAX_AVAILABILITY_DAYS = 93
TOP_RATED_LIMIT = 50
REVEAL_LIST_LIMIT = 50
PROVIDER_OR_ABOVE = [s for s, rank in STATUS_RANK.items() if rank >= STATUS_RANK["provider"]]
LEADER_STATUSES = ["verifier", "admin", "owner"]


def section(title: str, columns: list[str], rows: Sequence[Sequence[Any]]) -> Section:
    return Section(title, columns, [[cell(value) for value in row] for row in rows])


def code_of(column: Any) -> Any:
    """A short reference code for a person: the first 8 characters of the id."""
    return func.left(cast(column, String), 8)


def in_church(p: ReportParams, column: Any) -> list[ColumnElement[bool]]:
    return [column == p.church_id] if p.church_id is not None else []


def searchable_providers(p: ReportParams) -> list[ColumnElement[bool]]:
    """Open accounts of PROVIDER or above (the people a search can list) in the chosen church."""
    return [
        Person.closed_at.is_(None),
        Person.status.in_(PROVIDER_OR_ABOVE),
        exists().where(
            PersonLabel.person_id == Person.id,
            PersonLabel.label_id == Label.id,
            Label.label_type == "skill",
        ),
        *in_church(p, Person.church_id),
    ]


# ---- RP-01 ---------------------------------------------------------------------------------


def registrations_per_day(db: Session, p: ReportParams) -> list[Section]:
    day = cast(func.timezone(p.timezone, Person.created_at), Date)
    rows = db.execute(
        select(day, Church.name, Person.status, func.count())
        .select_from(Person)
        .join(Church, Church.id == Person.church_id)
        .where(Person.created_at >= p.start, Person.created_at < p.end, *in_church(p, Church.id))
        .group_by(day, Church.name, Person.status)
        .order_by(day, Church.name, Person.status)
    ).all()
    return [section("Sign-ups per day", ["day", "church", "status_now", "sign_ups"], rows)]


# ---- RP-02 ---------------------------------------------------------------------------------


def active_users(db: Session, p: ReportParams) -> list[Section]:
    statuses = [p.status] if p.status else list(STATUS_RANK)
    rows = []
    for status in statuses:
        active = db.scalar(
            select(func.count())
            .select_from(Person)
            .where(
                Person.status == status,
                Person.last_login_at >= p.start,
                Person.last_login_at < p.end,
                *in_church(p, Person.church_id),
            )
        )
        logins = (
            select(func.count())
            .select_from(LoginHistory)
            .join(Person, Person.id == LoginHistory.user_id)
            .where(
                Person.status == status,
                LoginHistory.login_time >= p.start,
                LoginHistory.login_time < p.end,
                *in_church(p, Person.church_id),
            )
        )
        ok = db.scalar(logins.where(LoginHistory.succeeded.is_(True)))
        failed = db.scalar(logins.where(LoginHistory.succeeded.is_(False)))
        rows.append((status, active or 0, ok or 0, failed or 0))
    if not p.status and p.church_id is None:
        # A failed attempt with an address nobody has belongs to no status and to no church.
        unknown = db.scalar(
            select(func.count())
            .select_from(LoginHistory)
            .where(
                LoginHistory.user_id.is_(None),
                LoginHistory.succeeded.is_(False),
                LoginHistory.login_time >= p.start,
                LoginHistory.login_time < p.end,
            )
        )
        rows.append(("unknown address", 0, 0, unknown or 0))
    return [
        section(
            "Active people and logins",
            ["status", "active_people", "successful_logins", "failed_logins"],
            rows,
        )
    ]


# ---- RP-03 ---------------------------------------------------------------------------------


def providers_by_label(db: Session, p: ReportParams) -> list[Section]:
    count = func.count(Person.id)
    rows = db.execute(
        select(Label.label_type, Label.label_name, count)
        .select_from(Label)
        .outerjoin(PersonLabel, PersonLabel.label_id == Label.id)
        .outerjoin(
            Person,
            and_(
                Person.id == PersonLabel.person_id,
                Person.closed_at.is_(None),
                Person.status.in_(PROVIDER_OR_ABOVE),
                *in_church(p, Person.church_id),
            ),
        )
        .where(Label.is_active.is_(True), Label.label_type != "skill_level")
        .group_by(Label.label_type, Label.label_name)
        .order_by(Label.label_type, count.desc(), Label.label_name)
    ).all()
    return [section("Providers by label", ["label_type", "label", "providers"], rows)]


# ---- RP-04 ---------------------------------------------------------------------------------


def top_rated(db: Session, p: ReportParams) -> list[Section]:
    average = func.avg(Rating.rating)
    count = func.count(Rating.id)
    in_window = and_(Rating.rated_on >= p.start, Rating.rated_on < p.end)
    top = db.execute(
        select(code_of(Rating.provider_id), average, count)
        .select_from(Rating)
        .join(Person, Person.id == Rating.provider_id)
        .where(in_window, *in_church(p, Person.church_id))
        .group_by(Rating.provider_id)
        .having(count >= p.min_ratings)
        .order_by(average.desc(), count.desc(), Rating.provider_id)
        .limit(TOP_RATED_LIMIT)
    ).all()
    per_skill = db.execute(
        select(Label.label_name, average, count, func.count(func.distinct(Rating.provider_id)))
        .select_from(Rating)
        .join(PersonLabel, PersonLabel.person_id == Rating.provider_id)
        .join(Label, and_(Label.id == PersonLabel.label_id, Label.label_type == "skill"))
        .join(Person, Person.id == Rating.provider_id)
        .where(in_window, *in_church(p, Person.church_id))
        .group_by(Label.label_name)
        .order_by(average.desc(), Label.label_name)
    ).all()
    return [
        section(
            f"Top rated providers (at least {p.min_ratings} rating(s))",
            ["provider_code", "average_rating", "ratings"],
            top,
        ),
        section(
            "Average rating per skill",
            ["skill", "average_rating", "ratings", "providers_rated"],
            per_skill,
        ),
    ]


# ---- RP-05 ---------------------------------------------------------------------------------


def verification_summary(db: Session, p: ReportParams) -> list[Section]:
    """People by status per church and home group, and what verifying did in the period."""
    group_id = func.coalesce(Person.home_group_id, Person.last_home_group_id)
    people = db.execute(
        select(
            Church.name,
            HomeGroup.name,
            func.count().filter(Person.status == "pending"),
            func.count().filter(Person.status == "searcher"),
            func.count().filter(Person.status == "provider"),
            func.count().filter(Person.status.in_(LEADER_STATUSES)),
            func.count().filter(Person.status == "revoked"),
        )
        .select_from(Person)
        .join(Church, Church.id == Person.church_id)
        .join(HomeGroup, HomeGroup.id == group_id)
        .where(Person.closed_at.is_(None), *in_church(p, Church.id))
        .group_by(Church.name, HomeGroup.name)
        .order_by(Church.name, HomeGroup.name)
    ).all()

    signup = aliased(StatusChange)
    admission = aliased(StatusChange)
    admitted_vouches = (
        select(func.count())
        .select_from(Vouch)
        .where(Vouch.applicant_id == admission.person_id, Vouch.withdrawn_at.is_(None))
        .correlate(admission)
        .scalar_subquery()
    )
    admissions = (
        select(
            Church.name,
            func.count(admission.id),
            func.avg(func.extract("epoch", admission.at - signup.at) / 86400.0),
            func.avg(admitted_vouches),
        )
        .select_from(admission)
        .join(Person, Person.id == admission.person_id)
        .join(Church, Church.id == Person.church_id)
        .outerjoin(signup, and_(signup.person_id == admission.person_id, signup.kind == "signup"))
        .where(
            admission.kind == "admit",
            admission.at >= p.start,
            admission.at < p.end,
            *in_church(p, Church.id),
        )
        .group_by(Church.name)
    )
    # Declining closes an applicant's account (decision D-27): an applicant whose account was
    # closed in the period is a decline, or one who left while waiting.
    declines = (
        select(Church.name, func.count())
        .select_from(Person)
        .join(Church, Church.id == Person.church_id)
        .where(
            Person.closed_at >= p.start,
            Person.closed_at < p.end,
            Person.status == "pending",
            *in_church(p, Church.id),
        )
        .group_by(Church.name)
    )
    admitted = {name: (n, days, vouches) for name, n, days, vouches in db.execute(admissions)}
    declined = dict(db.execute(declines).tuples().all())
    churches = sorted(set(admitted) | set(declined))
    period = [
        (
            name,
            admitted.get(name, (0, None, None))[0],
            declined.get(name, 0),
            admitted.get(name, (0, None, None))[1],
            admitted.get(name, (0, None, None))[2],
        )
        for name in churches
    ]
    return [
        section(
            "People by church, home group and status",
            ["church", "home_group", "pending", "searchers", "providers", "leaders", "revoked"],
            people,
        ),
        section(
            "Admissions and declines in the period",
            [
                "church",
                "admissions",
                "declines_or_left_while_pending",
                "average_days_from_sign_up_to_admission",
                "average_vouches_per_admission",
            ],
            period,
        ),
    ]


# ---- RP-06 ---------------------------------------------------------------------------------


def rate_distribution(db: Session, p: ReportParams) -> list[Section]:
    query = (
        select(
            Label.label_name,
            Person.rate_currency,
            func.count(Person.id),
            func.avg(Person.rate_per_hour),
            func.min(Person.rate_per_hour),
            func.max(Person.rate_per_hour),
        )
        .select_from(Person)
        .join(PersonLabel, PersonLabel.person_id == Person.id)
        .join(Label, and_(Label.id == PersonLabel.label_id, Label.label_type == "skill"))
        .where(
            Person.rate_per_hour.is_not(None),
            Person.closed_at.is_(None),
            Person.status.in_(PROVIDER_OR_ABOVE),
            *in_church(p, Person.church_id),
        )
        .group_by(Label.label_name, Person.rate_currency)
        .order_by(Label.label_name, Person.rate_currency)
    )
    if p.skill:
        query = query.where(func.lower(Label.label_name) == p.skill.lower())
    if p.currency:
        query = query.where(Person.rate_currency == p.currency.upper())
    rows = db.execute(query).all()
    return [
        section(
            "Hourly rate by skill and currency",
            ["skill", "currency", "providers", "average_rate", "min_rate", "max_rate"],
            rows,
        )
    ]


# ---- RP-07 ---------------------------------------------------------------------------------

_AVAILABILITY_SQL = text(
    """
    WITH days AS (
        SELECT d::date AS day
        FROM generate_series(CAST(:first AS date), CAST(:last AS date), interval '1 day') AS d
    ), searchable AS (
        SELECT p.id FROM people p
        WHERE p.closed_at IS NULL
          AND p.status IN ('provider', 'verifier', 'admin', 'owner')
          AND (CAST(:church AS uuid) IS NULL OR p.church_id = CAST(:church AS uuid))
          AND EXISTS (
              SELECT 1 FROM person_labels pl JOIN labels l ON l.id = pl.label_id
              WHERE pl.person_id = p.id AND l.label_type = 'skill'
          )
    )
    SELECT days.day,
           (SELECT count(*) FROM searchable) AS searchable_providers,
           count(DISTINCT u.person_id) AS unavailable
    FROM days
    LEFT JOIN person_unavailability u
      ON u.person_id IN (SELECT id FROM searchable)
     AND u.unavailable_from < ((days.day + 1)::timestamp AT TIME ZONE :tz)
     AND u.unavailable_to > (days.day::timestamp AT TIME ZONE :tz)
    GROUP BY days.day
    ORDER BY days.day
    """
)


def availability_overview(db: Session, p: ReportParams) -> list[Section]:
    zone = ZoneInfo(p.timezone)
    first = p.start.astimezone(zone).date()
    last = (p.end.astimezone(zone) - timedelta(microseconds=1)).date()
    if (last - first).days + 1 > MAX_AVAILABILITY_DAYS:
        raise ReportError(f"The availability report covers at most {MAX_AVAILABILITY_DAYS} days")
    result = db.execute(
        _AVAILABILITY_SQL,
        {"first": first, "last": last, "tz": p.timezone, "church": p.church_id},
    ).all()
    rows = [(day, total, unavailable, total - unavailable) for day, total, unavailable in result]
    return [
        section(
            "Availability of searchable providers",
            ["day", "searchable_providers", "unavailable", "available"],
            rows,
        )
    ]


# ---- RP-08 ---------------------------------------------------------------------------------


def phone_reveals(db: Session, p: ReportParams) -> list[Section]:
    """How often a number was revealed, who asked, and for whom (people shown by code)."""
    reveal = PhoneReveal
    in_window = and_(reveal.revealed_at >= p.start, reveal.revealed_at < p.end)
    if p.church_id is not None:  # the reveals of the providers of that church
        in_window = and_(
            in_window,
            exists().where(Person.id == reveal.provider_id, Person.church_id == p.church_id),
        )
    reveals = func.count(reveal.id)

    total, searchers, providers, dial, search = db.execute(
        select(
            reveals,
            func.count(func.distinct(reveal.revealer_id)),
            func.count(func.distinct(reveal.provider_id)),
            reveals.filter(reveal.channel == "dial"),
            reveals.filter(reveal.source == "search"),
        ).where(in_window)
    ).one()

    pairs = (
        select(
            reveal.revealer_id,
            reveal.provider_id,
            func.min(reveal.revealed_at).label("first_reveal"),
        )
        .where(in_window)
        .group_by(reveal.revealer_id, reveal.provider_id)
        .subquery()
    )
    pair_count = db.scalar(select(func.count()).select_from(pairs)) or 0
    # A pair counts as "rated afterwards" when the same person rated that provider after the reveal.
    rated_after = (
        db.scalar(
            select(func.count())
            .select_from(pairs)
            .where(
                exists().where(
                    Rating.rater_id == pairs.c.revealer_id,
                    Rating.provider_id == pairs.c.provider_id,
                    Rating.rated_on >= pairs.c.first_reveal,
                )
            )
        )
        or 0
    )
    summary = [
        ("reveals", total),
        ("searchers", searchers),
        ("providers_revealed", providers),
        ("reveals_on_phone_dialler", dial),
        ("reveals_shown_on_screen", total - dial),
        ("reveals_from_search_page", search),
        ("reveals_from_detail_page", total - search),
        ("searcher_provider_pairs", pair_count),
        ("pairs_rated_afterwards", rated_after),
        ("rated_afterwards_percent", round(100 * rated_after / pair_count, 1) if pair_count else 0),
    ]

    day = cast(func.timezone(p.timezone, reveal.revealed_at), Date)
    per_day = db.execute(
        select(day, reveal.channel, reveals)
        .where(in_window)
        .group_by(day, reveal.channel)
        .order_by(day, reveal.channel)
    ).all()

    per_searcher = db.execute(
        select(
            code_of(reveal.revealer_id),
            reveals,
            func.count(func.distinct(reveal.provider_id)),
            func.max(reveal.revealed_at),
        )
        .where(in_window)
        .group_by(reveal.revealer_id)
        .order_by(reveals.desc(), reveal.revealer_id)
        .limit(REVEAL_LIST_LIMIT)
    ).all()

    per_skill = db.execute(
        select(Label.label_name, reveals, func.count(func.distinct(reveal.provider_id)))
        .select_from(reveal)
        .join(PersonLabel, PersonLabel.person_id == reveal.provider_id)
        .join(Label, and_(Label.id == PersonLabel.label_id, Label.label_type == "skill"))
        .where(in_window)
        .group_by(Label.label_name)
        .order_by(reveals.desc(), Label.label_name)
    ).all()

    # The reveals' own skill lists, one row per skill. LATERAL lets the function read the
    # list of the reveal row it is joined to, so the reveal row must come first in FROM.
    # render_derived() names the output column (AS alias(skill)); unnest has no column name of
    # its own.
    searched = func.unnest(reveal.searched_skills).table_valued("skill").render_derived().lateral()
    per_searched = db.execute(
        select(searched.c.skill, func.count())
        .select_from(reveal)
        .join(searched, true())
        .where(in_window)
        .group_by(searched.c.skill)
        .order_by(func.count().desc(), searched.c.skill)
    ).all()

    most_revealed = db.execute(
        select(
            code_of(reveal.provider_id),
            reveals,
            func.count(func.distinct(reveal.revealer_id)),
        )
        .where(in_window)
        .group_by(reveal.provider_id)
        .order_by(reveals.desc(), reveal.provider_id)
        .limit(REVEAL_LIST_LIMIT)
    ).all()

    return [
        section("Mobile number reveals: summary", ["measure", "value"], summary),
        section("Reveals per day", ["day", "channel", "reveals"], per_day),
        section(
            "Reveals per searcher",
            ["searcher_code", "reveals", "providers", "last_reveal"],
            per_searcher,
        ),
        section("Reveals per skill of the provider", ["skill", "reveals", "providers"], per_skill),
        section("Skills searched for before a reveal", ["skill", "reveals"], per_searched),
        section(
            "Most revealed providers",
            ["provider_code", "reveals", "searchers"],
            most_revealed,
        ),
    ]


# ---- RP-09 ---------------------------------------------------------------------------------

TRUST_KINDS = ("revoke", "reinstate", "reconfirm", "appoint", "step-down", "handover")


def trust_events(db: Session, p: ReportParams) -> list[Section]:
    """Revocations, reinstatements, leader changes, closures and moves in the period."""
    kind_counts = db.execute(
        select(Church.name, StatusChange.kind, func.count())
        .select_from(StatusChange)
        .join(Person, Person.id == StatusChange.person_id)
        .join(Church, Church.id == Person.church_id)
        .where(
            StatusChange.kind.in_(TRUST_KINDS),
            StatusChange.at >= p.start,
            StatusChange.at < p.end,
            *in_church(p, Church.id),
        )
        .group_by(Church.name, StatusChange.kind)
        .order_by(Church.name, StatusChange.kind)
    ).all()
    flagged_now = db.execute(
        select(Church.name, func.count())
        .select_from(Person)
        .join(Church, Church.id == Person.church_id)
        .where(
            Person.flagged_for_recheck.is_(True),
            Person.closed_at.is_(None),
            *in_church(p, Church.id),
        )
        .group_by(Church.name)
        .order_by(Church.name)
    ).all()
    groups_closed = db.execute(
        select(Church.name, func.count())
        .select_from(HomeGroup)
        .join(Church, Church.id == HomeGroup.church_id)
        .where(
            HomeGroup.closed_at >= p.start,
            HomeGroup.closed_at < p.end,
            *in_church(p, Church.id),
        )
        .group_by(Church.name)
        .order_by(Church.name)
    ).all()
    churches_closed = (
        []
        if p.church_id is not None  # a church's ADMIN never reads about the closing of churches
        else db.execute(
            select(Church.name, Church.closed_at).where(
                Church.closed_at >= p.start, Church.closed_at < p.end
            )
        ).all()
    )
    moves = db.execute(
        select(Church.name, func.count())
        .select_from(MoveRequest)
        .join(Person, Person.id == MoveRequest.person_id)
        .join(Church, Church.id == Person.church_id)
        .where(
            MoveRequest.completed_at >= p.start,
            MoveRequest.completed_at < p.end,
            *in_church(p, Church.id),
        )
        .group_by(Church.name)
        .order_by(Church.name)
    ).all()
    return [
        section("Trust events by church and kind", ["church", "kind", "events"], kind_counts),
        section("People flagged for a re-check now", ["church", "flagged"], flagged_now),
        section("Home groups closed", ["church", "groups_closed"], groups_closed),
        section("Churches closed", ["church", "closed_at"], churches_closed),
        section("Moves between home groups completed", ["church", "moves"], moves),
    ]


# ---- scheduled reports ---------------------------------------------------------------------


def chat_reports(db: Session, p: ReportParams) -> list[Section]:
    """Reports of chat conversations: per reason and per week, open and handled. No names, no
    text, no conversation ids."""
    in_window = and_(ChatReport.created_at >= p.start, ChatReport.created_at < p.end)
    handled = ChatReport.handled_at.is_not(None)
    total, open_now, closed = db.execute(
        select(
            func.count(ChatReport.id),
            func.count(ChatReport.id).filter(ChatReport.handled_at.is_(None)),
            func.count(ChatReport.id).filter(handled),
        ).where(in_window)
    ).one()
    per_reason = db.execute(
        select(
            ChatReport.reason,
            func.count(ChatReport.id),
            func.count(ChatReport.id).filter(ChatReport.handled_at.is_(None)),
            func.count(ChatReport.id).filter(handled),
        )
        .where(in_window)
        .group_by(ChatReport.reason)
        .order_by(ChatReport.reason)
    ).all()
    week = func.date_trunc("week", func.timezone(p.timezone, ChatReport.created_at))
    per_week = db.execute(
        select(
            func.to_char(week, "YYYY-MM-DD"),
            func.count(ChatReport.id),
            func.count(ChatReport.id).filter(ChatReport.handled_at.is_(None)),
        )
        .where(in_window)
        .group_by(week)
        .order_by(week)
    ).all()
    return [
        section("Summary", ["reports", "open", "handled"], [[total, open_now, closed]]),
        section("By reason", ["reason", "reports", "open", "handled"], per_reason),
        section("By week (Monday)", ["week", "reports", "open"], per_week),
    ]


def signups_daily(db: Session, p: ReportParams) -> list[Section]:
    """New applicants in the window by what they ask to be (or their status now) and church."""
    asked = func.coalesce(Person.requested_status, Person.status)
    rows = db.execute(
        select(Church.name, asked, func.count())
        .select_from(Person)
        .join(Church, Church.id == Person.church_id)
        .where(Person.created_at >= p.start, Person.created_at < p.end, *in_church(p, Church.id))
        .group_by(Church.name, asked)
        .order_by(Church.name, asked)
    ).all()
    total = sum(row[2] for row in rows)
    return [
        section("New applicants by church and requested status", ["church", "status", "new"], rows),
        section("Total", ["measure", "value"], [("new_applicants", total)]),
    ]


def weekly_summary(db: Session, p: ReportParams) -> list[Section]:
    return [*verification_summary(db, p), *trust_events(db, p)]


def monthly_summary(db: Session, p: ReportParams) -> list[Section]:
    sections: list[Section] = []
    for build in (
        registrations_per_day,
        active_users,
        providers_by_label,
        top_rated,
        verification_summary,
        rate_distribution,
        availability_overview,
        phone_reveals,
        trust_events,
    ):
        sections.extend(build(db, p))
    return sections


REPORTS: list[ReportDef] = [
    ReportDef(
        "registrations_per_day",
        "RP-01",
        "Sign-ups per day",
        "New people per day, by church and by what they are now.",
        registrations_per_day,
        admin_scoped=True,
    ),
    ReportDef(
        "active_users",
        "RP-02",
        "Active people and logins",
        "People who logged in, and successful and failed logins, by status.",
        active_users,
        filters=("status",),
    ),
    ReportDef(
        "providers_by_label",
        "RP-03",
        "Providers by skill, language, nativity and timing",
        "How many providers have each label.",
        providers_by_label,
        admin_scoped=True,
    ),
    ReportDef(
        "top_rated",
        "RP-04",
        "Top rated providers and rating per skill",
        "Best rated providers (by code) and the average rating per skill.",
        top_rated,
        filters=("min_ratings",),
    ),
    ReportDef(
        "verification_summary",
        "RP-05",
        "Verification summary",
        "People by status per church and home group, admissions and declines in the period, "
        "days from sign-up to admission and vouches per admission.",
        verification_summary,
        admin_scoped=True,
    ),
    ReportDef(
        "rate_distribution",
        "RP-06",
        "Rate distribution by skill",
        "Average, minimum and maximum hourly rate per skill and currency.",
        rate_distribution,
        filters=("skill", "currency"),
    ),
    ReportDef(
        "availability_overview",
        "RP-07",
        "Provider availability overview",
        "Searchable providers available on each day (at most 93 days).",
        availability_overview,
        admin_scoped=True,
    ),
    ReportDef(
        "phone_reveals",
        "RP-08",
        "Mobile number reveals",
        "How often numbers were revealed: per day, per searcher, per skill, most revealed "
        "providers and how many reveals were followed by a rating.",
        phone_reveals,
    ),
    ReportDef(
        "trust_events",
        "RP-09",
        "Trust events",
        "Revocations, reinstatements, re-checks, leader changes, group and church closures "
        "and moves.",
        trust_events,
        admin_scoped=True,
    ),
    ReportDef(
        "chat_reports",
        "RP-10",
        "Chat reports",
        "Reported conversations in the period: per reason and per week, open and handled.",
        chat_reports,
    ),
    ReportDef(
        "signups_daily",
        "SC-01",
        "Sign-ups in the last day",
        "New applicants by requested status and church. Scheduled daily.",
        signups_daily,
    ),
    ReportDef(
        "weekly_summary",
        "SC-02",
        "Weekly summary",
        "The verification summary and the trust events. Scheduled weekly.",
        weekly_summary,
    ),
    ReportDef(
        "monthly_summary",
        "SC-03",
        "Monthly summary",
        "All standard reports for the month. Scheduled monthly.",
        monthly_summary,
        filters=("min_ratings",),
    ),
]
REGISTRY: dict[str, ReportDef] = {report.name: report for report in REPORTS}


def get_definition(name: str) -> ReportDef:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ReportError("Unknown report") from None
