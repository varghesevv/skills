"""Operator commands: setting up Skills with the first OWNER."""

import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Church, HomeGroup, Person, StatusChange
from app.services.operators import SetupError, create_first_owner

pytestmark = pytest.mark.db


def setup(session: Session, **overrides: str) -> tuple[str, str]:
    password = secrets.token_urlsafe(16)
    values = {
        "full_name": "Ada Owner",
        "email": "Owner@Example.com",
        "mobile_number": "+971500000100",
        "church_name": "First church",
        "group_name": "First group",
        **overrides,
    }
    create_first_owner(session, password=password, **values)
    return password, values["email"].lower()


@pytest.fixture(autouse=True)
def _empty_installation(session: Session) -> None:
    """These tests need a database without an OWNER; the test database may hold seed rows."""
    assert session.scalar(select(Person.id).where(Person.status == "owner")) is None


def test_setup_creates_the_owner_their_church_and_their_group(session: Session) -> None:
    password, email = setup(session)
    owner = session.scalars(select(Person).where(Person.email == email)).one()
    church = session.get(Church, owner.church_id)
    group = session.get(HomeGroup, owner.home_group_id)
    assert church is not None and group is not None
    assert (owner.status, owner.full_name, owner.mobile_number) == (
        "owner",
        "Ada Owner",
        "+971500000100",
    )
    assert church.admin_id == owner.id and church.name == "First church"
    assert group.leader_id == owner.id and group.church_id == church.id
    assert group.name == "First group"
    assert owner.password_hash is not None and owner.password_hash != password
    assert verify_password(owner.password_hash, password)
    assert owner.status_set_by_id is None


def test_setup_records_an_operator_change_in_the_history(session: Session) -> None:
    _password, email = setup(session)
    owner = session.scalars(select(Person).where(Person.email == email)).one()
    change = session.scalars(select(StatusChange).where(StatusChange.person_id == owner.id)).one()
    assert (change.from_status, change.to_status, change.kind, change.changed_by_id) == (
        None,
        "owner",
        "operator",
        None,
    )


def test_a_second_setup_is_refused_and_changes_nothing(session: Session) -> None:
    setup(session)
    before = session.scalar(select(Person.id).where(Person.status == "owner"))
    with pytest.raises(SetupError, match="already set up"):
        setup(session, email="other@example.com", mobile_number="+971500000101")
    assert session.scalar(select(Person.id).where(Person.status == "owner")) == before
    assert len(session.scalars(select(Church)).all()) == 1


def test_a_bad_name_is_refused_with_a_message_that_holds_no_detail(session: Session) -> None:
    with pytest.raises(SetupError) as error:
        setup(session, full_name="A")
    message = str(error.value)
    assert "Example.com" not in message and "owner@example.com" not in message
    assert session.scalar(select(Person.id).where(Person.status == "owner")) is None
