"""Database rules that protect data even if application code has a bug."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Freelancer,
    FreelancerLabel,
    FreelancerUnavailability,
    Label,
    LoginHistory,
    Organisation,
    OrgFreelancer,
    UserRating,
    WorkHost,
)

pytestmark = pytest.mark.db


def make_freelancer(email: str = "f@example.com", **extra: object) -> Freelancer:
    return Freelancer(
        user_email=email, mobile_number="+971500000001", password_hash="not-a-real-hash", **extra
    )


def make_work_host(email: str = "h@example.com") -> WorkHost:
    return WorkHost(user_email=email, mobile_number="+971500000002", password_hash="x")


def label(session: Session, label_type: str, name: str) -> Label:
    return session.scalars(
        select(Label).where(Label.label_type == label_type, Label.label_name == name)
    ).one()


def at(hour: int) -> datetime:
    return datetime(2026, 11, 1, hour, 0, tzinfo=UTC)


# ---- accounts ----------------------------------------------------------------------------


def test_duplicate_email_is_rejected(session: Session) -> None:
    session.add(make_freelancer())
    session.flush()
    session.add(make_freelancer())
    with pytest.raises(IntegrityError):
        session.flush()


def test_uppercase_email_is_rejected(session: Session) -> None:
    session.add(make_freelancer("Mixed@Example.com"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_new_account_gets_defaults(session: Session) -> None:
    host = make_work_host()
    session.add(host)
    session.flush()
    session.refresh(host)
    assert host.id is not None
    assert host.avail_sun is False
    assert host.created_at is not None
    assert host.last_login_at is None


def test_rate_needs_a_currency(session: Session) -> None:
    session.add(make_freelancer(rate_per_hour=25))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("currency", ["aed", "AE", "A1B"])
def test_bad_currency_is_rejected(session: Session, currency: str) -> None:
    session.add(make_freelancer(rate_per_hour=25, rate_currency=currency))
    with pytest.raises(IntegrityError):
        session.flush()


def test_currency_longer_than_three_letters_is_rejected(session: Session) -> None:
    session.add(make_freelancer(rate_per_hour=25, rate_currency="DIRHAM"))
    with pytest.raises(DBAPIError):
        session.flush()


def test_negative_rate_is_rejected(session: Session) -> None:
    session.add(make_freelancer(rate_per_hour=-1, rate_currency="AED"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_valid_rate_is_accepted(session: Session) -> None:
    session.add(make_freelancer(rate_per_hour=25.5, rate_currency="AED"))
    session.flush()


# ---- labels ------------------------------------------------------------------------------


def test_duplicate_label_is_rejected(session: Session) -> None:
    session.add(Label(label_name="plumbing", label_type="skill"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unknown_label_type_is_rejected(session: Session) -> None:
    session.add(Label(label_name="x", label_type="colour"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_skill_with_level_is_accepted(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add(
        FreelancerLabel(
            freelancer_id=freelancer.id,
            label_id=label(session, "skill", "plumbing").id,
            level_label_id=label(session, "skill_level", "80%").id,
        )
    )
    session.flush()


def test_level_on_a_non_skill_label_is_rejected(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add(
        FreelancerLabel(
            freelancer_id=freelancer.id,
            label_id=label(session, "language", "English").id,
            level_label_id=label(session, "skill_level", "basic").id,
        )
    )
    with pytest.raises(DBAPIError):
        session.flush()


def test_level_must_be_a_skill_level_label(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add(
        FreelancerLabel(
            freelancer_id=freelancer.id,
            label_id=label(session, "skill", "plumbing").id,
            level_label_id=label(session, "language", "English").id,
        )
    )
    with pytest.raises(DBAPIError):
        session.flush()


# ---- vouching ----------------------------------------------------------------------------


def test_vouch_starts_pending_and_active(session: Session) -> None:
    freelancer = make_freelancer()
    organisation = Organisation(
        org_name="Care Co",
        user_email="o@example.com",
        mobile_number="+971500000003",
        password_hash="x",
    )
    session.add_all([freelancer, organisation])
    session.flush()
    vouch = OrgFreelancer(org_id=organisation.id, freelancer_id=freelancer.id)
    session.add(vouch)
    session.flush()
    session.refresh(vouch)
    assert vouch.status == "pending"
    assert vouch.is_active is True


# ---- availability ------------------------------------------------------------------------


def test_unavailability_must_end_after_it_starts(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add(
        FreelancerUnavailability(
            freelancer_id=freelancer.id, unavailable_from=at(10), unavailable_to=at(10)
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_overlapping_unavailability_is_rejected(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add(
        FreelancerUnavailability(
            freelancer_id=freelancer.id, unavailable_from=at(8), unavailable_to=at(12)
        )
    )
    session.flush()
    session.add(
        FreelancerUnavailability(
            freelancer_id=freelancer.id, unavailable_from=at(11), unavailable_to=at(14)
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_back_to_back_unavailability_is_accepted(session: Session) -> None:
    freelancer = make_freelancer()
    session.add(freelancer)
    session.flush()
    session.add_all(
        [
            FreelancerUnavailability(
                freelancer_id=freelancer.id, unavailable_from=at(8), unavailable_to=at(12)
            ),
            FreelancerUnavailability(
                freelancer_id=freelancer.id, unavailable_from=at(12), unavailable_to=at(14)
            ),
        ]
    )
    session.flush()


# ---- ratings and login history -------------------------------------------------------------


def _host_and_freelancer(session: Session) -> tuple[WorkHost, Freelancer]:
    host, freelancer = make_work_host(), make_freelancer()
    session.add_all([host, freelancer])
    session.flush()
    return host, freelancer


@pytest.mark.parametrize("value", [1, 5, 10])
def test_valid_rating_is_accepted(session: Session, value: int) -> None:
    host, freelancer = _host_and_freelancer(session)
    session.add(UserRating(work_host_id=host.id, freelancer_id=freelancer.id, rating=value))
    session.flush()


@pytest.mark.parametrize("value", [-1, 0, 11])
def test_rating_out_of_range_is_rejected(session: Session, value: int) -> None:
    host, freelancer = _host_and_freelancer(session)
    session.add(UserRating(work_host_id=host.id, freelancer_id=freelancer.id, rating=value))
    with pytest.raises(IntegrityError):
        session.flush()


def test_second_rating_for_same_pair_is_rejected(session: Session) -> None:
    host, freelancer = _host_and_freelancer(session)
    session.add(UserRating(work_host_id=host.id, freelancer_id=freelancer.id, rating=7))
    session.flush()
    session.add(UserRating(work_host_id=host.id, freelancer_id=freelancer.id, rating=9))
    with pytest.raises(IntegrityError):
        session.flush()


def test_login_history_accepts_unknown_user(session: Session) -> None:
    entry = LoginHistory(user_type="freelancer", login_email="nobody@example.com", succeeded=False)
    session.add(entry)
    session.flush()
    session.refresh(entry)
    assert entry.user_id is None
    assert entry.login_time is not None


def test_login_history_rejects_unknown_user_type(session: Session) -> None:
    session.add(LoginHistory(user_type="robot", login_email="x@example.com", succeeded=True))
    with pytest.raises(IntegrityError):
        session.flush()
