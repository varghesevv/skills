"""Generates a believable, repeatable demo data set (all fake people and companies).

    organisations, work hosts and freelancers with different skills, skill levels, timings,
    languages and nativity; organisations vouching for freelancers; work hosts rating them;
    some planned unavailability; registration dates spread over the last 60 days.

The same seed always gives the same people, so a run can be repeated or reset. Every account
uses the one DEMO_USER_PASSWORD given by the caller; passwords are hashed once here and never
logged or printed. All emails end with DEMO_DATA_DOMAIN so they can be found and removed again.
"""

import itertools
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Freelancer,
    FreelancerLabel,
    FreelancerUnavailability,
    Label,
    Organisation,
    OrgFreelancer,
    UserRating,
    WorkHost,
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

ORG_NAMES = [
    ("Gulf Care Staffing", "approved"),
    ("Al Noor Facility Services", "approved"),
    ("Desert Fix Maintenance", "approved"),
    ("Skyline Technical Services", "approved"),
    ("Keralam Workers Association", "approved"),
    ("Marina Home Services", "approved"),
    ("Falcon Manpower Solutions", "approved"),
    ("Oasis Community Helpers", "approved"),
    ("Bright Hands Cooperative", "pending"),
    ("Sunrise Contractors", "rejected"),
]

HOST_FIRST = ["Hassan", "Layla", "Omar", "Mariam", "Khalid", "Aisha", "Yusuf", "Noor", "Tariq"]
HOST_FIRST += ["Salma", "Faisal", "Huda", "Rashid", "Amna", "Saeed", "Reem", "Zayed", "Dana"]
HOST_LAST = ["Al Mansoori", "Al Hashimi", "Khan", "Siddiqui", "Al Falasi", "Haddad", "Nasser"]
HOST_LAST += ["Qureshi", "Al Ketbi", "Farouk", "Abdullah", "Mirza", "Al Suwaidi", "Rahimi"]

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

PERMUTATION_SIZES = (1, 1, 2, 2, 3)  # how many skills a freelancer has


@dataclass(frozen=True)
class CredentialRow:
    user_type: str
    email: str
    name: str
    status: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _mobile(index: int) -> str:
    return f"+97150{index:07d}"


def _labels(db: Session) -> dict[tuple[str, str], Label]:
    found = {(label.label_type, label.label_name): label for label in db.scalars(select(Label))}
    if not found:
        raise RuntimeError("No labels found; run the database migrations first.")
    return found


def remove_generated(db: Session) -> int:
    """Delete every account created by this module (children go with them)."""
    removed = 0
    for model in (Freelancer, WorkHost, Organisation):
        result = db.execute(delete(model).where(model.user_email.like(f"%@{DEMO_DATA_DOMAIN}")))
        removed += int(result.rowcount or 0)  # type: ignore[attr-defined]
    db.commit()
    return removed


def generate(
    db: Session,
    password: str,
    *,
    organisations: int = 10,
    work_hosts: int = 50,
    freelancers: int = 200,
    seed: int = 2026,
) -> list[CredentialRow]:
    """Create the data set and return one row per account (no passwords inside)."""
    # Not for security: a seeded generator makes the fake data repeatable.
    rng = random.Random(seed)  # noqa: S311
    now = _utc_now()
    password_hash = hash_password(password)  # hashed once; every demo account shares it
    labels = _labels(db)
    skills = sorted(name for kind, name in labels if kind == "skill")
    levels = [labels[("skill_level", name)] for name in ("basic", "50%", "80%")]
    timings = sorted(name for kind, name in labels if kind == "timing")

    def created_at() -> datetime:
        return now - timedelta(days=rng.uniform(0, 60), hours=rng.uniform(0, 12))

    rows: list[CredentialRow] = []
    taken: set[str] = set()

    def email_for(first: str, last: str) -> str:
        base = f"{first}.{last}".lower().replace(" ", "")
        for n in itertools.count(rng.randint(1, 99)):
            email = f"{base}{n}@{DEMO_DATA_DOMAIN}"
            if email not in taken:
                taken.add(email)
                return email
        raise AssertionError("unreachable")

    # --- organisations -------------------------------------------------------------------
    org_rows: list[Organisation] = []
    for index in range(organisations):
        name, status = ORG_NAMES[index % len(ORG_NAMES)]
        if index >= len(ORG_NAMES):
            name = f"{name} {index // len(ORG_NAMES) + 1}"
        slug = name.lower().replace(" ", ".")
        email = f"admin.{slug}@{DEMO_DATA_DOMAIN}"
        taken.add(email)
        stamp = created_at()
        org = Organisation(
            user_email=email,
            mobile_number=_mobile(100000 + index),
            password_hash=password_hash,
            org_name=name,
            approval_status=status,
            approved_at=stamp + timedelta(days=1) if status == "approved" else None,
            created_at=stamp,
            updated_at=stamp,
        )
        org_rows.append(org)
        rows.append(CredentialRow("organisation", email, name, status))
    db.add_all(org_rows)

    # --- work hosts ----------------------------------------------------------------------
    host_rows: list[WorkHost] = []
    for index in range(work_hosts):
        first, last = rng.choice(HOST_FIRST), rng.choice(HOST_LAST)
        email = email_for(first, last.replace(" ", ""))
        stamp = created_at()
        days = {
            f"avail_{day}": rng.random() < 0.7
            for day in ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
        }
        host = WorkHost(
            user_email=email,
            mobile_number=_mobile(200000 + index),
            password_hash=password_hash,
            full_name=f"{first} {last}",
            created_at=stamp,
            updated_at=stamp,
            **days,
        )
        host_rows.append(host)
        rows.append(CredentialRow("workhost", email, host.full_name or "", "active"))
    db.add_all(host_rows)

    # --- freelancers ---------------------------------------------------------------------
    group_names = list(GROUP_WEIGHTS)
    group_weights = list(GROUP_WEIGHTS.values())
    free_rows: list[Freelancer] = []
    used_groups: list[str] = []
    label_rows: list[FreelancerLabel] = []
    unavail_rows: list[FreelancerUnavailability] = []
    for index in range(freelancers):
        group_name = rng.choices(group_names, group_weights)[0]
        group = GROUPS[group_name]
        used_groups.append(group_name)
        first = rng.choice(group["first"])  # type: ignore[arg-type]
        last = rng.choice(group["last"])  # type: ignore[arg-type]
        email = email_for(first, last)
        stamp = created_at()
        has_rate = rng.random() < 0.85
        freelancer = Freelancer(
            user_email=email,
            mobile_number=_mobile(300000 + index),
            password_hash=password_hash,
            full_name=f"{first} {last}",
            nationality=str(group["nationality"]),
            primary_language=str(group["language"]),
            whatsapp_availability=rng.random() < 0.8,
            rate_per_hour=Decimal(rng.randrange(15, 81, 5)) if has_rate else None,
            rate_currency="AED" if has_rate else None,
            is_rate_negotiable=rng.random() < 0.4,
            created_at=stamp,
            updated_at=stamp,
        )
        free_rows.append(freelancer)
        rows.append(CredentialRow("freelancer", email, freelancer.full_name or "", "active"))
    db.add_all(free_rows)
    db.flush()  # ids are needed for the child rows

    for freelancer, group_name in zip(free_rows, used_groups, strict=True):
        group = GROUPS[group_name]
        bias = SKILL_BIAS.get(group_name, {})
        weights = [2 + bias.get(skill, 0) for skill in skills]
        picked: list[str] = []
        while len(picked) < rng.choice(PERMUTATION_SIZES):
            choice = rng.choices(skills, weights)[0]
            if choice not in picked:
                picked.append(choice)
        for skill in picked:
            label_rows.append(
                FreelancerLabel(
                    freelancer_id=freelancer.id,
                    label_id=labels[("skill", skill)].id,
                    level_label_id=rng.choices(levels, [3, 4, 3])[0].id,
                )
            )
        for timing in rng.sample(timings, rng.choice((1, 1, 2, 3))):
            label_rows.append(
                FreelancerLabel(
                    freelancer_id=freelancer.id, label_id=labels[("timing", timing)].id
                )
            )
        spoken = set(group["labels"])  # type: ignore[call-overload]
        if rng.random() < 0.3:
            spoken.add(rng.choice(["English", "Hindi", "Tamil"]))
        for language in sorted(spoken):
            label_rows.append(
                FreelancerLabel(
                    freelancer_id=freelancer.id, label_id=labels[("language", language)].id
                )
            )
        label_rows.append(
            FreelancerLabel(
                freelancer_id=freelancer.id,
                label_id=labels[("nativity", str(group["nativity"]))].id,
            )
        )
        if rng.random() < 0.25:  # planned time off, never overlapping
            start = (now + timedelta(days=rng.randint(2, 20))).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            for _ in range(rng.choice((1, 2))):
                end = start + timedelta(days=rng.randint(1, 5))
                unavail_rows.append(
                    FreelancerUnavailability(
                        freelancer_id=freelancer.id, unavailable_from=start, unavailable_to=end
                    )
                )
                start = end + timedelta(days=rng.randint(3, 10))
    db.add_all(label_rows)
    db.add_all(unavail_rows)

    # --- vouching (approved organisations only) ----------------------------------------
    vouches: list[OrgFreelancer] = []
    for org in org_rows:
        if org.approval_status != "approved":
            continue
        count = min(len(free_rows), rng.randint(15, 40))
        for freelancer in rng.sample(free_rows, count):
            status = rng.choices(["approved", "pending", "revoked"], [75, 15, 10])[0]
            vouches.append(
                OrgFreelancer(
                    org_id=org.id,
                    freelancer_id=freelancer.id,
                    status=status,
                    is_active=status != "revoked",
                )
            )
    db.add_all(vouches)

    # --- ratings by work hosts ---------------------------------------------------------
    ratings: list[UserRating] = []
    for host in host_rows:
        for freelancer in rng.sample(free_rows, min(len(free_rows), rng.randint(5, 14))):
            score = rng.choices(range(1, 11), [1, 1, 1, 2, 4, 6, 12, 18, 18, 12])[0]
            band = "high" if score >= 8 else "mid" if score >= 5 else "low"
            ratings.append(
                UserRating(
                    work_host_id=host.id,
                    freelancer_id=freelancer.id,
                    rating=score,
                    comment=rng.choice(RATING_COMMENTS[band]) if rng.random() < 0.7 else None,
                )
            )
    db.add_all(ratings)
    db.commit()
    return rows
