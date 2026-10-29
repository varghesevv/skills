"""The report queries. Each returns sections (a title, columns and rows)."""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Date,
    Select,
    and_,
    cast,
    exists,
    func,
    literal_column,
    select,
    text,
    true,
    union_all,
)
from sqlalchemy.orm import Session

from app.models.auth import LoginHistory
from app.models.labels import FreelancerLabel, Label
from app.models.ratings import UserRating
from app.models.reveals import PhoneReveal
from app.models.users import Admin, Freelancer, Organisation, WorkHost
from app.models.vouching import OrgFreelancer
from app.reports.types import ReportDef, ReportError, ReportParams, Section, cell

MAX_AVAILABILITY_DAYS = 93
TOP_RATED_LIMIT = 50
REVEAL_LIST_LIMIT = 50
SELF_REGISTERED = (
    ("freelancer", Freelancer),
    ("workhost", WorkHost),
    ("organisation", Organisation),
)
ALL_ACCOUNTS = (*SELF_REGISTERED, ("admin", Admin))


def section(title: str, columns: list[str], rows: Sequence[Sequence[Any]]) -> Section:
    return Section(title, columns, [[cell(value) for value in row] for row in rows])


# ---- RP-01 ---------------------------------------------------------------------------------


def registrations_per_day(db: Session, p: ReportParams) -> list[Section]:
    parts: list[Select[Any]] = [
        select(
            cast(func.timezone(p.timezone, model.created_at), Date).label("day"),
            literal_column(f"'{user_type}'").label("user_type"),
            func.count().label("registrations"),
        )
        .where(model.created_at >= p.start, model.created_at < p.end)
        .group_by(literal_column("1"))
        for user_type, model in SELF_REGISTERED
    ]
    rows = db.execute(union_all(*parts).order_by(literal_column("1"), literal_column("2"))).all()
    return [section("Registrations per day", ["day", "user_type", "registrations"], rows)]


# ---- RP-02 ---------------------------------------------------------------------------------


def active_users(db: Session, p: ReportParams) -> list[Section]:
    rows = []
    for user_type, model in ALL_ACCOUNTS:
        if p.user_type not in (None, user_type):
            continue
        active = db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.last_login_at >= p.start, model.last_login_at < p.end)
        )
        logins = (
            select(func.count())
            .select_from(LoginHistory)
            .where(
                LoginHistory.user_type == user_type,
                LoginHistory.login_time >= p.start,
                LoginHistory.login_time < p.end,
            )
        )
        ok = db.scalar(logins.where(LoginHistory.succeeded.is_(True)))
        failed = db.scalar(logins.where(LoginHistory.succeeded.is_(False)))
        rows.append((user_type, active or 0, ok or 0, failed or 0))
    return [
        section(
            "Active users and logins",
            ["user_type", "active_users", "successful_logins", "failed_logins"],
            rows,
        )
    ]


# ---- RP-03 ---------------------------------------------------------------------------------


def freelancers_by_label(db: Session, p: ReportParams) -> list[Section]:
    count = func.count(FreelancerLabel.freelancer_id)
    rows = db.execute(
        select(Label.label_type, Label.label_name, count)
        .select_from(Label)
        .outerjoin(FreelancerLabel, FreelancerLabel.label_id == Label.id)
        .where(Label.is_active.is_(True), Label.label_type != "skill_level")
        .group_by(Label.label_type, Label.label_name)
        .order_by(Label.label_type, count.desc(), Label.label_name)
    ).all()
    return [section("Freelancers by label", ["label_type", "label", "freelancers"], rows)]


# ---- RP-04 ---------------------------------------------------------------------------------


def top_rated(db: Session, p: ReportParams) -> list[Section]:
    average = func.avg(UserRating.rating)
    count = func.count(UserRating.id)
    in_window = and_(UserRating.rated_on >= p.start, UserRating.rated_on < p.end)
    top = db.execute(
        select(UserRating.freelancer_id, average, count)
        .where(in_window)
        .group_by(UserRating.freelancer_id)
        .having(count >= p.min_ratings)
        .order_by(average.desc(), count.desc(), UserRating.freelancer_id)
        .limit(TOP_RATED_LIMIT)
    ).all()
    per_skill = db.execute(
        select(
            Label.label_name,
            average,
            count,
            func.count(func.distinct(UserRating.freelancer_id)),
        )
        .select_from(UserRating)
        .join(FreelancerLabel, FreelancerLabel.freelancer_id == UserRating.freelancer_id)
        .join(Label, and_(Label.id == FreelancerLabel.label_id, Label.label_type == "skill"))
        .where(in_window)
        .group_by(Label.label_name)
        .order_by(average.desc(), Label.label_name)
    ).all()
    return [
        section(
            f"Top rated freelancers (at least {p.min_ratings} rating(s))",
            ["freelancer_id", "average_rating", "ratings"],
            top,
        ),
        section(
            "Average rating per skill",
            ["skill", "average_rating", "ratings", "freelancers_rated"],
            per_skill,
        ),
    ]


# ---- RP-05 ---------------------------------------------------------------------------------


def vouching_summary(db: Session, p: ReportParams) -> list[Section]:
    link = OrgFreelancer.freelancer_id
    query = (
        select(
            Organisation.id,
            Organisation.org_name,
            func.count(link),
            func.count(link).filter(
                and_(OrgFreelancer.status == "approved", OrgFreelancer.is_active.is_(True))
            ),
            func.count(link).filter(OrgFreelancer.status == "pending"),
            func.count(link).filter(OrgFreelancer.is_active.is_(False)),
        )
        .select_from(Organisation)
        .outerjoin(OrgFreelancer, OrgFreelancer.org_id == Organisation.id)
        .where(Organisation.approval_status == "approved")
        .group_by(Organisation.id, Organisation.org_name)
        .order_by(Organisation.org_name, Organisation.id)
    )
    if p.org_id is not None:
        query = query.where(Organisation.id == p.org_id)
    rows = db.execute(query).all()
    return [
        section(
            "Organisation vouching summary",
            ["org_id", "organisation", "freelancers", "active", "pending", "inactive"],
            rows,
        )
    ]


# ---- RP-06 ---------------------------------------------------------------------------------


def rate_distribution(db: Session, p: ReportParams) -> list[Section]:
    query = (
        select(
            Label.label_name,
            Freelancer.rate_currency,
            func.count(Freelancer.id),
            func.avg(Freelancer.rate_per_hour),
            func.min(Freelancer.rate_per_hour),
            func.max(Freelancer.rate_per_hour),
        )
        .select_from(Freelancer)
        .join(FreelancerLabel, FreelancerLabel.freelancer_id == Freelancer.id)
        .join(Label, and_(Label.id == FreelancerLabel.label_id, Label.label_type == "skill"))
        .where(Freelancer.rate_per_hour.is_not(None))
        .group_by(Label.label_name, Freelancer.rate_currency)
        .order_by(Label.label_name, Freelancer.rate_currency)
    )
    if p.skill:
        query = query.where(func.lower(Label.label_name) == p.skill.lower())
    if p.currency:
        query = query.where(Freelancer.rate_currency == p.currency.upper())
    rows = db.execute(query).all()
    return [
        section(
            "Hourly rate by skill and currency",
            ["skill", "currency", "freelancers", "average_rate", "min_rate", "max_rate"],
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
        SELECT id FROM freelancers WHERE rate_per_hour IS NOT NULL
    )
    SELECT days.day,
           (SELECT count(*) FROM searchable) AS searchable_freelancers,
           count(DISTINCT u.freelancer_id) AS unavailable
    FROM days
    LEFT JOIN freelancer_unavailability u
      ON u.freelancer_id IN (SELECT id FROM searchable)
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
    result = db.execute(_AVAILABILITY_SQL, {"first": first, "last": last, "tz": p.timezone}).all()
    rows = [(day, total, unavailable, total - unavailable) for day, total, unavailable in result]
    return [
        section(
            "Availability of searchable freelancers",
            ["day", "searchable_freelancers", "unavailable", "available"],
            rows,
        )
    ]


# ---- RP-08 ---------------------------------------------------------------------------------


def phone_reveals(db: Session, p: ReportParams) -> list[Section]:
    """How often work hosts asked for a mobile number, who asked, and for whom."""
    in_window = and_(PhoneReveal.revealed_at >= p.start, PhoneReveal.revealed_at < p.end)
    reveals = func.count(PhoneReveal.id)

    total, hosts, freelancers, dial, search = db.execute(
        select(
            reveals,
            func.count(func.distinct(PhoneReveal.work_host_id)),
            func.count(func.distinct(PhoneReveal.freelancer_id)),
            reveals.filter(PhoneReveal.channel == "dial"),
            reveals.filter(PhoneReveal.source == "search"),
        ).where(in_window)
    ).one()

    pairs = (
        select(
            PhoneReveal.work_host_id,
            PhoneReveal.freelancer_id,
            func.min(PhoneReveal.revealed_at).label("first_reveal"),
        )
        .where(in_window)
        .group_by(PhoneReveal.work_host_id, PhoneReveal.freelancer_id)
        .subquery()
    )
    pair_count = db.scalar(select(func.count()).select_from(pairs)) or 0
    # A pair counts as "rated afterwards" when the same host rated that freelancer after the reveal.
    rated_after = (
        db.scalar(
            select(func.count())
            .select_from(pairs)
            .where(
                exists().where(
                    UserRating.work_host_id == pairs.c.work_host_id,
                    UserRating.freelancer_id == pairs.c.freelancer_id,
                    UserRating.rated_on >= pairs.c.first_reveal,
                )
            )
        )
        or 0
    )
    summary = [
        ("reveals", total),
        ("work_hosts", hosts),
        ("freelancers_revealed", freelancers),
        ("reveals_on_phone_dialler", dial),
        ("reveals_shown_on_screen", total - dial),
        ("reveals_from_search_page", search),
        ("reveals_from_detail_page", total - search),
        ("host_freelancer_pairs", pair_count),
        ("pairs_rated_afterwards", rated_after),
        ("rated_afterwards_percent", round(100 * rated_after / pair_count, 1) if pair_count else 0),
    ]

    day = cast(func.timezone(p.timezone, PhoneReveal.revealed_at), Date)
    per_day = db.execute(
        select(day, PhoneReveal.channel, reveals)
        .where(in_window)
        .group_by(day, PhoneReveal.channel)
        .order_by(day, PhoneReveal.channel)
    ).all()

    per_host = db.execute(
        select(
            PhoneReveal.work_host_id,
            WorkHost.full_name,
            reveals,
            func.count(func.distinct(PhoneReveal.freelancer_id)),
            func.max(PhoneReveal.revealed_at),
        )
        .join(WorkHost, WorkHost.id == PhoneReveal.work_host_id)
        .where(in_window)
        .group_by(PhoneReveal.work_host_id, WorkHost.full_name)
        .order_by(reveals.desc(), WorkHost.full_name, PhoneReveal.work_host_id)
        .limit(REVEAL_LIST_LIMIT)
    ).all()

    per_skill = db.execute(
        select(Label.label_name, reveals, func.count(func.distinct(PhoneReveal.freelancer_id)))
        .select_from(PhoneReveal)
        .join(FreelancerLabel, FreelancerLabel.freelancer_id == PhoneReveal.freelancer_id)
        .join(Label, and_(Label.id == FreelancerLabel.label_id, Label.label_type == "skill"))
        .where(in_window)
        .group_by(Label.label_name)
        .order_by(reveals.desc(), Label.label_name)
    ).all()

    # The reveals' own skill lists, one row per skill. LATERAL lets the function read the
    # list of the reveal row it is joined to, so the reveal row must come first in FROM.
    searched = func.unnest(PhoneReveal.searched_skills).table_valued("skill").lateral()
    per_searched = db.execute(
        select(searched.c.skill, func.count())
        .select_from(PhoneReveal)
        .join(searched, true())
        .where(in_window)
        .group_by(searched.c.skill)
        .order_by(func.count().desc(), searched.c.skill)
    ).all()

    most_revealed = db.execute(
        select(
            PhoneReveal.freelancer_id,
            Freelancer.full_name,
            reveals,
            func.count(func.distinct(PhoneReveal.work_host_id)),
        )
        .join(Freelancer, Freelancer.id == PhoneReveal.freelancer_id)
        .where(in_window)
        .group_by(PhoneReveal.freelancer_id, Freelancer.full_name)
        .order_by(reveals.desc(), Freelancer.full_name, PhoneReveal.freelancer_id)
        .limit(REVEAL_LIST_LIMIT)
    ).all()

    return [
        section("Mobile number reveals: summary", ["measure", "value"], summary),
        section("Reveals per day", ["day", "channel", "reveals"], per_day),
        section(
            "Reveals per work host",
            ["work_host_id", "work_host", "reveals", "freelancers", "last_reveal"],
            per_host,
        ),
        section(
            "Reveals per skill of the freelancer", ["skill", "reveals", "freelancers"], per_skill
        ),
        section("Skills searched for before a reveal", ["skill", "reveals"], per_searched),
        section(
            "Most revealed freelancers",
            ["freelancer_id", "freelancer", "reveals", "work_hosts"],
            most_revealed,
        ),
    ]


# ---- scheduled reports ---------------------------------------------------------------------


def users_registered(db: Session, p: ReportParams) -> list[Section]:
    counts: list[tuple[str, int]] = []
    people: list[tuple[Any, ...]] = []
    for user_type, model in SELF_REGISTERED:
        rows = db.execute(
            select(model.id, model.user_email, model.created_at)
            .where(model.created_at >= p.start, model.created_at < p.end)
            .order_by(model.created_at, model.id)
        ).all()
        counts.append((user_type, len(rows)))
        people.extend((user_type, *row) for row in rows)
    people.sort(key=lambda row: str(row[3]))
    return [
        section("New users by type", ["user_type", "new_users"], counts),
        section("New users", ["user_type", "id", "email", "registered_at"], people),
    ]


def weekly_summary(db: Session, p: ReportParams) -> list[Section]:
    return [*top_rated(db, p), *vouching_summary(db, p)]


def monthly_summary(db: Session, p: ReportParams) -> list[Section]:
    sections: list[Section] = []
    for build in (
        registrations_per_day,
        active_users,
        freelancers_by_label,
        top_rated,
        vouching_summary,
        rate_distribution,
        availability_overview,
        phone_reveals,
    ):
        sections.extend(build(db, p))
    return sections


REPORTS: list[ReportDef] = [
    ReportDef(
        "registrations_per_day",
        "RP-01",
        "Registrations per day",
        "New accounts per day and user type.",
        registrations_per_day,
    ),
    ReportDef(
        "active_users",
        "RP-02",
        "Active users and logins",
        "Users who logged in, and successful and failed logins.",
        active_users,
        filters=("user_type",),
    ),
    ReportDef(
        "freelancers_by_label",
        "RP-03",
        "Freelancers by skill, language, nativity and timing",
        "How many freelancers have each label.",
        freelancers_by_label,
    ),
    ReportDef(
        "top_rated",
        "RP-04",
        "Top rated freelancers and rating per skill",
        "Best rated freelancers and the average rating per skill.",
        top_rated,
        filters=("min_ratings",),
    ),
    ReportDef(
        "vouching_summary",
        "RP-05",
        "Organisation vouching summary",
        "Freelancers per organisation, active and inactive.",
        vouching_summary,
        filters=("org_id",),
        org_scoped=True,
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
        "Freelancer availability overview",
        "Searchable freelancers available on each day (at most 93 days).",
        availability_overview,
    ),
    ReportDef(
        "phone_reveals",
        "RP-08",
        "Mobile number reveals",
        "How often work hosts revealed mobile numbers: per day, per work host, per skill, "
        "most revealed freelancers and how many reveals were followed by a rating.",
        phone_reveals,
    ),
    ReportDef(
        "users_registered_daily",
        "SC-01",
        "Users registered in the last day",
        "New freelancers, work hosts and organisations with counts and rows. Scheduled daily.",
        users_registered,
    ),
    ReportDef(
        "weekly_summary",
        "SC-02",
        "Weekly summary",
        "Top rated freelancers and the vouching summary. Scheduled weekly.",
        weekly_summary,
        filters=("min_ratings",),
    ),
    ReportDef(
        "monthly_summary",
        "SC-03",
        "Monthly summary",
        "All standard reports for the month. Scheduled monthly.",
        monthly_summary,
    ),
]
REGISTRY: dict[str, ReportDef] = {report.name: report for report in REPORTS}


def get_definition(name: str) -> ReportDef:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ReportError("Unknown report") from None
