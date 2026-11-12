"""Operator commands: setting up Skills with the first OWNER."""

import io
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.core.config import get_settings
from app.core.security import verify_password
from app.models import Church, HomeGroup, Person, StatusChange
from app.services import operators
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


def test_two_setups_at_once_report_that_skills_is_already_set_up(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second run passes the owner check, but the database allows one OWNER."""
    setup(session)
    calls = iter([False, True])  # first look: none yet (the other run was not committed)
    monkeypatch.setattr(operators, "_owner_exists", lambda _db: next(calls))
    with pytest.raises(SetupError, match="already set up"):
        setup(session, email="other@example.com", mobile_number="+971500000101")


def test_a_value_the_database_refuses_is_reported_not_raised(session: Session) -> None:
    with pytest.raises(SetupError):
        setup(session, church_name="x" * 300)  # longer than the column


# ---- the command itself ------------------------------------------------------------------------


@contextmanager
def _use(session: Session) -> Iterator[Session]:
    yield session  # the test session stays open and is rolled back by the fixture


@pytest.fixture
def command(session: Session, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run `python -m app.cli ...` in process, on the test session, with a password on stdin."""
    monkeypatch.setattr(cli, "sessionmaker", lambda **_kwargs: lambda: _use(session))

    def run(*args: str, password: str) -> int:
        monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
        return cli.main(list(args) + ["--password-stdin"])

    return run


OWNER_ARGS = (
    "create-owner", "--name", "Ada Owner", "--email", "ada@example.com",
    "--mobile", "+971 50 000 0100", "--church", "First church", "--group", "First group",
)  # fmt: skip


def test_create_owner_command_sets_up_skills(
    command: Any, session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    password = secrets.token_urlsafe(16)
    assert command(*OWNER_ARGS, password=password) == 0
    owner = session.scalars(select(Person).where(Person.email == "ada@example.com")).one()
    assert owner.status == "owner" and owner.mobile_number == "+971500000100"
    output = capsys.readouterr()
    assert "OWNER created" in output.out
    assert password not in output.out + output.err
    assert owner.password_hash is not None and password not in owner.password_hash


def test_create_owner_command_refuses_a_second_owner(
    command: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    password = secrets.token_urlsafe(16)
    assert command(*OWNER_ARGS, password=password) == 0
    other = [a if a != "ada@example.com" else "bob@example.com" for a in OWNER_ARGS]
    other[other.index("+971 50 000 0100")] = "+971500000101"
    assert command(*other, password=password) == 1
    output = capsys.readouterr()
    assert "already set up" in output.err and password not in output.out + output.err


@pytest.mark.parametrize(
    ("replace", "message"),
    [
        (("+971 50 000 0100", "12"), "mobile number"),
        (("ada@example.com", "ada-at-example"), "email"),
        (("Ada Owner", "A"), "at least 2"),
        (("First church", "  "), "must not be empty"),
        (("First group", "g" * 201), "at most 200"),
    ],
)
def test_create_owner_command_refuses_bad_input(
    command: Any,
    session: Session,
    capsys: pytest.CaptureFixture[str],
    replace: tuple[str, str],
    message: str,
) -> None:
    args = [replace[1] if a == replace[0] else a for a in OWNER_ARGS]
    assert command(*args, password=secrets.token_urlsafe(16)) == 1
    assert message in capsys.readouterr().err
    assert session.scalar(select(Person.id).where(Person.status == "owner")) is None


def test_create_owner_command_refuses_a_short_password(
    command: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(*OWNER_ARGS, password="short") == 1
    output = capsys.readouterr()
    assert "Password must be" in output.err and "short" not in output.err.replace("short:", "")


def test_a_weak_password_is_refused_in_prod(
    command: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    get_settings.cache_clear()
    try:
        assert command(*OWNER_ARGS, password="abcdefghij") == 1  # long enough, but not strong
        assert "strong" in capsys.readouterr().err
    finally:
        get_settings.cache_clear()


def test_create_admin_still_works_after_the_shared_password_check(
    command: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    password = secrets.token_urlsafe(16)
    args = ("create-admin", "--email", "old-admin@example.com", "--mobile", "+971500000150")
    assert command(*args, password=password) == 0
    assert command(*args, password=password) == 1  # the second one is refused
    output = capsys.readouterr()
    assert "already exists" in output.err and password not in output.out + output.err
