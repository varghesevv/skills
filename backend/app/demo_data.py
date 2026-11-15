"""Generates a believable, repeatable demo data set (all fake people), over the church model.

Churches with an ADMIN each, home groups with a leader each, and people of every status:
providers with skills, skill levels, timings, languages, nativity and planned unavailability;
searchers who rate providers and reveal their numbers; applicants with vouches; and a few
revoked people. Every person has a history (sign-up, admission by their leader, revocation), and
dates are spread over the last 60 days. A short named cast comes first, so a demo has people to
log in as whatever the seed.

The same seed always gives the same people. Every account uses the one DEMO_USER_PASSWORD given
by the caller; passwords are hashed once here and never logged or printed. All emails end with
DEMO_DATA_DOMAIN. Status history is append-only, so the data cannot be removed row by row:
starting over is wiping the demo database (see the operations runbook).

The history is backdated: it has the rows of the changes (sign-up, admission, appointment,
revocation) but no notifications, so a demo person's notification list starts empty.
"""

import itertools
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Church,
    HomeGroup,
    Label,
    Person,
    PersonLabel,
    PersonUnavailability,
    PhoneReveal,
    Rating,
    StatusChange,
    Vouch,
)

DEMO_DATA_DOMAIN = "demo.example.com"

# --- name pools (fictional combinations) ---------------------------------------------------

# group -> (nativity label, nationality, primary language, first names, last names, extra languages)
GROUPS: dict[str, dict[str, object]] = {
    "indian": {
        "nativity": "Indian",
        "nationality": "Indian",
        "language": "Hindi",
        "first": ["Anita", "Rahul", "Priya", "Vikram", "Sunita", "Amit", "Neha", "Rohan", "Kavita"],
        "last": ["Sharma", "Verma", "Gupta", "Singh", "Mehta", "Yadav", "Joshi", "Kapoor"],
        "labels": ["Hindi", "English"],
    },
    "keralite": {
        "nativity": "Keralite",
        "nationality": "Indian",
        "language": "Malayalam",
        "first": ["Joseph", "Anil", "Deepa", "Biju", "Sreeja", "Thomas", "Reshma", "Sajan"],
        "last": ["Thomas", "Nair", "Varghese", "Menon", "Pillai", "Mathew", "George", "Kurian"],
        "labels": ["English", "Tamil"],
    },
    "tamil": {
        "nativity": "Indian",
        "nationality": "Indian",
        "language": "Tamil",
        "first": ["Karthik", "Lakshmi", "Murugan", "Divya", "Senthil", "Meena", "Arun", "Selvi"],
        "last": ["Subramanian", "Rajan", "Krishnan", "Iyer", "Pandian", "Sundaram", "Natarajan"],
        "labels": ["Tamil", "English"],
    },
    "srilankan": {
        "nativity": "Srilankan",
        "nationality": "Sri Lankan",
        "language": "Tamil",
        "first": ["Nimal", "Kumari", "Suresh", "Dilani", "Ruwan", "Shalini", "Chamara", "Thilini"],
        "last": ["Perera", "Fernando", "Silva", "Jayawardena", "Wickramasinghe", "Rathnayake"],
        "labels": ["Tamil", "English"],
    },
    "bangla": {
        "nativity": "Bangla",
        "nationality": "Bangladeshi",
        "language": "Bengali",
        "first": ["Rahim", "Fatima", "Kamal", "Nasrin", "Jamal", "Shirin", "Imran", "Rokeya"],
        "last": ["Hossain", "Rahman", "Khan", "Akter", "Chowdhury", "Islam", "Uddin", "Begum"],
        "labels": ["Hindi", "English"],
    },
    "philippines": {
        "nativity": "Philippines",
        "nationality": "Filipino",
        "language": "English",
        "first": ["Maria", "Jose", "Grace", "Mark", "Angelica", "Paolo", "Joy", "Ronald", "Liza"],
        "last": ["Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza", "Ramos", "Aquino"],
        "labels": ["English"],
    },
}
GROUP_WEIGHTS = {
    "indian": 25,
    "keralite": 20,
    "tamil": 12,
    "srilankan": 10,
    "bangla": 13,
    "philippines": 20,
}

# Skills each group is a little more likely to have (weight added to the base weight of 2).
SKILL_BIAS = {
    "philippines": {"patientcare": 6, "assistance": 4},
    "keralite": {"patientcare": 4, "electrical": 2},
    "bangla": {"plumbing": 4},
    "tamil": {"electrical": 3, "networking": 3},
    "indian": {"networking": 2, "plumbing": 2},
    "srilankan": {"assistance": 3},
}

RATING_COMMENTS = {
    "high": [
        "Arrived on time and finished the job neatly.",
        "Very professional, would book again.",
        "Clear communication and fair price.",
        "Fixed the problem quickly and explained what was done.",
        "Reliable and respectful of the home.",
    ],
    "mid": [
        "Good work, but arrived a little late.",
        "Job done well; needed a second visit for a small item.",
        "Friendly and capable, communication could be quicker.",
    ],
    "low": [
        "Work was incomplete and needed to be redone.",
        "Cancelled at short notice.",
    ],
}


PERMUTATION_SIZES = (1, 1, 2, 2, 3)  # how many skills a provider has

CHURCH_NAMES = ["Grace Church", "Hope Church", "Faith Church", "Mercy Church", "Light Church"]
GROUP_NAMES = ["Riverside", "Harbour", "Hillview", "Lakeside", "Meadow", "Oakwood", "Seaview"]
STATUS_WEIGHTS = {"provider": 50, "searcher": 30, "pending": 12, "revoked": 8}

# The named cast: a person for every role, so a demo has someone to log in as.
CAST = (
    ("owner", "Olive Owner"),
    ("admin", "Ada Admin"),
    ("leader", "Lena Leader"),
    ("provider", "Priya Provider"),
    ("searcher", "Sam Searcher"),
    ("applicant", "Ann Applicant"),
    ("revoked", "Rex Revoked"),
)


@dataclass(frozen=True)
class CredentialRow:
    status: str
    email: str
    name: str
    church: str
    home_group: str | None


class DemoDataExists(Exception):
    """Demo people are already in the database; starting over means wiping it."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _mobile(index: int) -> str:
    return f"+97156{index:07d}"


def _labels(db: Session) -> dict[tuple[str, str], Label]:
    found = {(label.label_type, label.label_name): label for label in db.scalars(select(Label))}
    if not found:
        raise RuntimeError("No labels found; run the database migrations first.")
    return found


def has_generated(db: Session) -> bool:
    return (
        db.scalar(select(Person.id).where(Person.email.like(f"%@{DEMO_DATA_DOMAIN}")).limit(1))
        is not None
    )


def generate(
    db: Session,
    password: str,
    *,
    churches: int = 3,
    groups_per_church: int = 3,
    people: int = 200,
    seed: int = 2026,
) -> list[CredentialRow]:
    """Create the data set and return one row per account (no passwords inside).

    Raises `DemoDataExists` when demo people are already there. An OWNER who exists already (the
    real one) keeps their church, which receives groups and people like the others.
    """
    if has_generated(db):
        raise DemoDataExists
    # Not for security: a seeded generator makes the fake data repeatable.
    rng = random.Random(seed)  # noqa: S311
    now = _utc_now()
    password_hash = hash_password(password)  # hashed once; every demo account shares it
    labels = _labels(db)
    skills = sorted(name for kind, name in labels if kind == "skill")
    levels = [labels[("skill_level", name)] for name in ("basic", "50%", "80%")]
    timings = sorted(name for kind, name in labels if kind == "timing")
    taken_emails: set[str] = set()
    counter = itertools.count(1)

    def moment(days_ago_max: float = 60, days_ago_min: float = 0) -> datetime:
        return now - timedelta(
            days=rng.uniform(days_ago_min, days_ago_max), hours=rng.uniform(0, 12)
        )

    def email_for(first: str, last: str) -> str:
        base = f"{first}.{last}".lower().replace(" ", "")
        for n in itertools.count(rng.randint(1, 99)):
            email = f"{base}{n}@{DEMO_DATA_DOMAIN}"
            if email not in taken_emails:
                taken_emails.add(email)
                return email
        raise AssertionError("unreachable")

    rows: list[CredentialRow] = []
    history: list[StatusChange] = []

    def person(
        first: str,
        last: str,
        status: str,
        church: Church,
        group: HomeGroup | None,
        **extra: object,
    ) -> Person:
        n = next(counter)
        email = extra.pop("email", None) or email_for(first, last)
        created = extra.pop("created_at", None) or moment()
        row = Person(
            id=uuid.uuid4(),
            status=status,
            church_id=church.id,
            home_group_id=group.id if group is not None and status != "revoked" else None,
            full_name=f"{first} {last}",
            email=str(email),
            mobile_number=_mobile(n),
            password_hash=password_hash,
            created_at=created,
            updated_at=created,
            **extra,
        )
        rows.append(
            CredentialRow(
                status,
                str(email),
                f"{first} {last}",
                church.name,
                group.name if group is not None and status != "revoked" else None,
            )
        )
        return row

    def record(
        who: Person, from_status: str | None, to: str, by: Person | None, kind: str, at: datetime
    ) -> None:
        history.append(
            StatusChange(
                person_id=who.id,
                from_status=from_status,
                to_status=to,
                changed_by_id=by.id if by else None,
                kind=kind,
                at=at,
            )
        )

    # --- churches, groups, ADMINs and leaders -------------------------------------------------
    existing_owner = db.scalar(
        select(Person).where(Person.status == "owner", Person.closed_at.is_(None))
    )
    all_people: list[Person] = []
    leaders: dict[uuid.UUID, Person] = {}  # group id -> leader
    group_rows: list[tuple[Church, HomeGroup]] = []
    people_by_group: dict[uuid.UUID, list[Person]] = {}
    owner = existing_owner
    for index in range(churches):
        name = CHURCH_NAMES[index % len(CHURCH_NAMES)]
        if index >= len(CHURCH_NAMES):
            name = f"{name} {index // len(CHURCH_NAMES) + 1}"
        if index == 0 and existing_owner is not None:
            church = db.get_one(Church, existing_owner.church_id)
            first_group = db.get_one(HomeGroup, existing_owner.home_group_id)
            head: Person = existing_owner
        else:
            first, last = (
                ("Olive", "Owner")
                if index == 0
                else ("Ada", "Admin" if index == 1 else f"Admin{index}")
            )
            status = "owner" if index == 0 else "admin"
            head_id = uuid.uuid4()
            first_created = moment(90, 60)
            church = Church(id=uuid.uuid4(), name=name, admin_id=head_id)
            db.add(church)
            db.flush()
            first_group = HomeGroup(
                id=uuid.uuid4(),
                church_id=church.id,
                name=GROUP_NAMES[0],
                leader_id=head_id,
                created_at=first_created,
            )
            db.add(first_group)
            db.flush()
            head = person(
                first,
                last,
                status,
                church,
                first_group,
                email=f"{first}.{last}@{DEMO_DATA_DOMAIN}".lower(),
                created_at=first_created,
            )
            head.id = head_id
            db.add(head)
            if index:
                head.status_set_by_id = owner.id if owner is not None else None
            record(
                head,
                None,
                status,
                owner if index else None,
                "operator" if index == 0 else "appoint",
                head.created_at,
            )
            if index == 0:
                owner = head
            all_people.append(head)
        group_rows.append((church, first_group))
        leaders[first_group.id] = head
        people_by_group[first_group.id] = []
        for g in range(1, groups_per_church):
            group_id, leader_id = uuid.uuid4(), uuid.uuid4()
            group_created = moment(75, 60)  # the leader is appointed when the group begins
            group = HomeGroup(
                id=group_id,
                church_id=church.id,
                name=GROUP_NAMES[g % len(GROUP_NAMES)] + ("" if g < len(GROUP_NAMES) else f" {g}"),
                leader_id=leader_id,
                created_at=group_created,
            )
            db.add(group)
            db.flush()
            fn, ln = (
                ("Lena", "Leader")
                if (index, g) == (0, 1)
                else (rng.choice(["Leo", "Lara", "Luke"]), f"Leader{index}{g}")
            )
            leader = person(fn, ln, "verifier", church, group, created_at=group_created)
            leader.id = leader_id
            db.add(leader)
            leader.status_set_by_id = head.id
            record(leader, None, "verifier", head, "appoint", leader.created_at)
            group_rows.append((church, group))
            leaders[group_id] = leader
            people_by_group[group_id] = []
            all_people.append(leader)
    db.flush()
    church_of = {group.id: church for church, group in group_rows}
    group_of = {group.id: group for _, group in group_rows}

    # --- the people ------------------------------------------------------------------------
    group_ids = [group.id for _, group in group_rows]
    statuses = list(STATUS_WEIGHTS)
    weights = list(STATUS_WEIGHTS.values())
    cast_roles = [role for role, _ in CAST[3:]]  # provider/searcher/applicant/revoked
    cast_status = {
        "provider": "provider",
        "searcher": "searcher",
        "applicant": "pending",
        "revoked": "revoked",
    }
    members: list[tuple[Person, str]] = []
    admitted_at: dict[uuid.UUID, datetime] = {}
    for index in range(people):
        group_id = (
            group_ids[index % len(group_ids)] if index < len(cast_roles) else rng.choice(group_ids)
        )
        church, group, leader = church_of[group_id], group_of[group_id], leaders[group_id]
        # One origin per person: their name, nationality, languages, nativity and skills agree.
        nat_key = rng.choices(list(GROUP_WEIGHTS), list(GROUP_WEIGHTS.values()))[0]
        if index < len(cast_roles):  # the named cast, in the first groups
            role = cast_roles[index]
            status = cast_status[role]
            first, last = dict(CAST)[role].split(" ", 1)
            email: object = f"{first}.{last}@{DEMO_DATA_DOMAIN}".lower()
            taken_emails.add(str(email))
        else:
            status = rng.choices(statuses, weights)[0]
            pool = GROUPS[nat_key]
            first, last = rng.choice(pool["first"]), rng.choice(pool["last"])  # type: ignore[arg-type]
            email = None
        pool = GROUPS[nat_key]
        # Admitted and revoked people signed up long enough ago for their history to be in the past.
        created = moment(58, 25) if status != "pending" else moment(30, 0)
        has_rate = rng.random() < 0.85
        profile: dict[str, object] = {}
        if status == "provider":
            profile = {
                "nationality": str(pool["nationality"]),
                "primary_language": str(pool["language"]),
                "whatsapp_availability": rng.random() < 0.8,
                "rate_per_hour": Decimal(rng.randrange(15, 81, 5)) if has_rate else None,
                "rate_currency": "AED" if has_rate else None,
                "is_rate_negotiable": rng.random() < 0.4,
            }
        extra: dict[str, object] = dict(profile)
        if email is not None:
            extra["email"] = email
        extra["created_at"] = created
        if status == "pending":
            extra["requested_status"] = rng.choice(["searcher", "provider"])
        row = person(first, last, status, church, group, **extra)
        if status in ("searcher", "provider"):
            row.status_set_by_id = leader.id
        if status == "revoked":
            row.last_home_group_id = group.id
            row.status_set_by_id = leader.id
        db.add(row)
        record(row, None, "pending", None, "signup", created)
        if status in ("searcher", "provider"):
            admitted_at[row.id] = created + timedelta(days=rng.uniform(0.2, 4))
            record(row, "pending", status, leader, "admit", admitted_at[row.id])
        elif status == "revoked":
            via = rng.choice(["searcher", "provider"])
            record(row, "pending", via, leader, "admit", created + timedelta(days=1))
            record(
                row, via, "revoked", leader, "revoke", created + timedelta(days=rng.uniform(2, 20))
            )
        people_by_group[group_id].append(row)
        all_people.append(row)
        members.append((row, nat_key))
    db.flush()

    # --- labels and unavailability for the providers ---------------------------------------
    label_rows: list[PersonLabel] = []
    unavail_rows: list[PersonUnavailability] = []
    providers = [row for row, _ in members if row.status == "provider"]
    for row, nat_key in members:
        if row.status != "provider":
            continue
        pool = GROUPS[nat_key]
        bias = SKILL_BIAS.get(nat_key, {})
        skill_weights = [2 + bias.get(skill, 0) for skill in skills]
        picked: list[str] = []
        while len(picked) < rng.choice(PERMUTATION_SIZES):
            choice = rng.choices(skills, skill_weights)[0]
            if choice not in picked:
                picked.append(choice)
        for skill in picked:
            label_rows.append(
                PersonLabel(
                    person_id=row.id,
                    label_id=labels[("skill", skill)].id,
                    level_label_id=rng.choices(levels, [3, 4, 3])[0].id,
                )
            )
        for timing in rng.sample(timings, rng.choice((1, 1, 2, 3))):
            label_rows.append(PersonLabel(person_id=row.id, label_id=labels[("timing", timing)].id))
        spoken = set(pool["labels"])  # type: ignore[call-overload]
        if rng.random() < 0.3:
            spoken.add(rng.choice(["English", "Hindi", "Tamil"]))
        for language in sorted(spoken):
            label_rows.append(
                PersonLabel(person_id=row.id, label_id=labels[("language", language)].id)
            )
        label_rows.append(
            PersonLabel(person_id=row.id, label_id=labels[("nativity", str(pool["nativity"]))].id)
        )
        if rng.random() < 0.25:  # planned time off, never overlapping
            start = (now + timedelta(days=rng.randint(2, 20))).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            for _ in range(rng.choice((1, 2))):
                end = start + timedelta(days=rng.randint(1, 5))
                unavail_rows.append(
                    PersonUnavailability(
                        person_id=row.id, unavailable_from=start, unavailable_to=end
                    )
                )
                start = end + timedelta(days=rng.randint(3, 10))
    db.add_all(label_rows)
    db.add_all(unavail_rows)

    # --- vouches for applicants, by admitted people of their church -------------------------
    admitted = [row for row, _ in members if row.status in ("searcher", "provider")]
    vouches: list[Vouch] = []
    for row, _ in members:
        if row.status != "pending":
            continue
        same_church = [a for a in admitted if a.church_id == row.church_id]
        for voucher in rng.sample(same_church, min(len(same_church), rng.choice((0, 1, 2, 3)))):
            vouches.append(Vouch(applicant_id=row.id, voucher_id=voucher.id))
    db.add_all(vouches)

    # --- ratings and reveals: admitted people look at providers -----------------------------
    ratings: list[Rating] = []
    reveals: list[PhoneReveal] = []
    for rater in admitted:
        for target in rng.sample(providers, min(len(providers), rng.randint(2, 8))):
            if target.id == rater.id:
                continue
            score = rng.choices(range(1, 11), [1, 1, 1, 2, 4, 6, 12, 18, 18, 12])[0]
            band = "high" if score >= 8 else "mid" if score >= 5 else "low"
            # After both of them were admitted, and before now.
            start = max(admitted_at[rater.id], admitted_at[target.id])
            when = start + (now - start) * rng.random()
            ratings.append(
                Rating(
                    rater_id=rater.id,
                    provider_id=target.id,
                    rating=score,
                    comment=rng.choice(RATING_COMMENTS[band]) if rng.random() < 0.7 else None,
                    rated_on=when,
                )
            )
            if rng.random() < 0.5:
                reveals.append(
                    PhoneReveal(
                        revealer_id=rater.id,
                        provider_id=target.id,
                        revealed_at=max(start, when - timedelta(minutes=rng.randint(1, 60))),
                        channel=rng.choice(["dial", "show"]),
                        source=rng.choice(["search", "detail"]),
                    )
                )
    db.add_all(ratings)
    db.add_all(reveals)
    db.add_all(history)
    db.commit()
    return rows
