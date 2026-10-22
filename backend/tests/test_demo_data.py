import secrets

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.demo_data import DEMO_DATA_DOMAIN, generate, remove_generated
from app.models import (
    Freelancer,
    FreelancerLabel,
    Organisation,
    OrgFreelancer,
    UserRating,
    WorkHost,
)

pytestmark = pytest.mark.db

PASSWORD = secrets.token_urlsafe(24)  # made up per run, never stored


def test_generates_requested_numbers_and_unique_logins(session: Session) -> None:
    rows = generate(session, PASSWORD, organisations=10, work_hosts=12, freelancers=30)
    assert [r.user_type for r in rows].count("organisation") == 10
    assert [r.user_type for r in rows].count("workhost") == 12
    assert [r.user_type for r in rows].count("freelancer") == 30
    assert len({r.email for r in rows}) == len(rows)
    assert all(r.email.endswith(f"@{DEMO_DATA_DOMAIN}") for r in rows)
    assert session.scalar(select(func.count()).select_from(Freelancer)) == 30
    assert session.scalar(select(func.count()).select_from(FreelancerLabel)) > 30 * 4
    assert session.scalar(select(func.count()).select_from(OrgFreelancer)) > 0
    assert session.scalar(select(func.count()).select_from(UserRating)) > 0
    statuses = set(session.scalars(select(Organisation.approval_status)))
    assert statuses == {"approved", "pending", "rejected"}


def test_same_seed_gives_same_people_and_reset_removes_them(session: Session) -> None:
    first = generate(session, PASSWORD, organisations=10, work_hosts=3, freelancers=5)
    assert remove_generated(session) == 18
    again = generate(session, PASSWORD, organisations=10, work_hosts=3, freelancers=5)
    assert [r.email for r in first] == [r.email for r in again]
    assert session.scalar(select(func.count()).select_from(WorkHost)) == 3
