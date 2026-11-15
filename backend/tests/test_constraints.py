"""Database rules that protect data even if application code has a bug (labels, time off,
ratings and the authentication tables of people; the rules of the church itself are in
`test_trust_schema.py`)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Label,
    LoginHistory,
    PasswordResetToken,
    Person,
    PersonLabel,
    PersonUnavailability,
    Rating,
    RefreshToken,
)
from tests.trust_helpers import World

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def label(session: Session, label_type: str, name: str) -> Label:
    return session.scalars(
        select(Label).where(Label.label_type == label_type, Label.label_name == name)
    ).one()


def at(hour: int) -> datetime:
    return datetime(2026, 11, 1, hour, 0, tzinfo=UTC)


def provider(world: World) -> Person:
    return world.add_person("provider")


# ---- labels ------------------------------------------------------------------------------


def test_duplicate_label_is_rejected(session: Session) -> None:
    session.add(Label(label_name="plumbing", label_type="skill"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unknown_label_type_is_rejected(session: Session) -> None:
    session.add(Label(label_name="x", label_type="colour"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_skill_with_level_is_accepted(session: Session, world: World) -> None:
    person = provider(world)
    session.add(
        PersonLabel(
            person_id=person.id,
            label_id=label(session, "skill", "plumbing").id,
            level_label_id=label(session, "skill_level", "80%").id,
        )
    )
    session.flush()


def test_level_on_a_non_skill_label_is_rejected(session: Session, world: World) -> None:
    person = provider(world)
    session.add(
        PersonLabel(
            person_id=person.id,
            label_id=label(session, "language", "English").id,
            level_label_id=label(session, "skill_level", "basic").id,
        )
    )
    with pytest.raises(DBAPIError):
        session.flush()


def test_level_must_be_a_skill_level_label(session: Session, world: World) -> None:
    person = provider(world)
    session.add(
        PersonLabel(
            person_id=person.id,
            label_id=label(session, "skill", "plumbing").id,
            level_label_id=label(session, "language", "English").id,
        )
    )
    with pytest.raises(DBAPIError):
        session.flush()


# ---- time off ----------------------------------------------------------------------------


def test_unavailability_must_end_after_it_starts(session: Session, world: World) -> None:
    person = provider(world)
    session.add(
        PersonUnavailability(person_id=person.id, unavailable_from=at(10), unavailable_to=at(10))
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_overlapping_unavailability_is_rejected(session: Session, world: World) -> None:
    person = provider(world)
    session.add(
        PersonUnavailability(person_id=person.id, unavailable_from=at(8), unavailable_to=at(12))
    )
    session.flush()
    session.add(
        PersonUnavailability(person_id=person.id, unavailable_from=at(11), unavailable_to=at(14))
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_back_to_back_unavailability_is_accepted(session: Session, world: World) -> None:
    person = provider(world)
    session.add_all(
        [
            PersonUnavailability(
                person_id=person.id, unavailable_from=at(8), unavailable_to=at(12)
            ),
            PersonUnavailability(
                person_id=person.id, unavailable_from=at(12), unavailable_to=at(14)
            ),
        ]
    )
    session.flush()


# ---- ratings -----------------------------------------------------------------------------


def _rater_and_provider(world: World) -> tuple[Person, Person]:
    return world.add_person("searcher"), provider(world)


@pytest.mark.parametrize("value", [1, 5, 10])
def test_valid_rating_is_accepted(session: Session, world: World, value: int) -> None:
    rater, target = _rater_and_provider(world)
    session.add(Rating(rater_id=rater.id, provider_id=target.id, rating=value))
    session.flush()


@pytest.mark.parametrize("value", [-1, 0, 11])
def test_rating_out_of_range_is_rejected(session: Session, world: World, value: int) -> None:
    rater, target = _rater_and_provider(world)
    session.add(Rating(rater_id=rater.id, provider_id=target.id, rating=value))
    with pytest.raises(IntegrityError):
        session.flush()


def test_second_rating_for_same_pair_is_rejected(session: Session, world: World) -> None:
    rater, target = _rater_and_provider(world)
    session.add(Rating(rater_id=rater.id, provider_id=target.id, rating=7))
    session.flush()
    session.add(Rating(rater_id=rater.id, provider_id=target.id, rating=9))
    with pytest.raises(IntegrityError):
        session.flush()


def test_nobody_rates_themselves(session: Session, world: World) -> None:
    target = provider(world)
    session.add(Rating(rater_id=target.id, provider_id=target.id, rating=9))
    with pytest.raises(IntegrityError):
        session.flush()


# ---- login history and tokens --------------------------------------------------------------


def test_login_history_accepts_unknown_user(session: Session) -> None:
    entry = LoginHistory(login_email="nobody@example.com", succeeded=False)
    session.add(entry)
    session.flush()
    session.refresh(entry)
    assert entry.user_id is None
    assert entry.login_time is not None


def test_login_history_points_at_a_person_or_nobody(session: Session) -> None:
    session.add(LoginHistory(user_id=uuid.uuid4(), login_email="x@example.com", succeeded=True))
    with pytest.raises(IntegrityError):
        session.flush()


def test_tokens_belong_to_a_person(session: Session) -> None:
    expires = datetime(2030, 1, 1, tzinfo=UTC)
    session.add(RefreshToken(user_id=uuid.uuid4(), token_hash="a" * 64, expires_at=expires))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    session.add(PasswordResetToken(user_id=uuid.uuid4(), token_hash="b" * 64, expires_at=expires))
    with pytest.raises(IntegrityError):
        session.flush()
