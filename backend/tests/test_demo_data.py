import secrets

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.demo_data import (
    CAST,
    DEMO_DATA_DOMAIN,
    CredentialRow,
    DemoDataExists,
    generate,
    has_generated,
)
from app.models import (
    Church,
    HomeGroup,
    Person,
    PersonLabel,
    PersonUnavailability,
    Rating,
    StatusChange,
    Vouch,
)
from tests.trust_helpers import check_rules

pytestmark = pytest.mark.db

PASSWORD = secrets.token_urlsafe(24)  # made up per run, never stored


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_generates_the_model_with_every_rule_holding(session: Session) -> None:
    rows = generate(session, PASSWORD, churches=3, groups_per_church=3, people=60)
    check_rules(session)  # the database accepts the whole state
    assert len({r.email for r in rows}) == len(rows)
    assert all(r.email.endswith(f"@{DEMO_DATA_DOMAIN}") for r in rows)
    assert count(session, Church) == 3
    assert count(session, HomeGroup) == 9
    statuses = [r.status for r in rows]
    assert statuses.count("owner") == 1
    assert statuses.count("admin") == 2
    assert statuses.count("verifier") == 6  # the leader of every group but the first of a church
    assert {"provider", "searcher", "pending", "revoked"} <= set(statuses)
    assert len(rows) == 3 + 6 + 60
    assert count(session, PersonLabel) > 20 * 4
    assert count(session, Rating) > 0
    assert count(session, Vouch) >= 0


def test_every_person_has_a_history_and_the_trust_chain_holds(session: Session) -> None:
    generate(session, PASSWORD, churches=2, groups_per_church=2, people=40)
    people = session.scalars(select(Person)).all()
    signups = set(
        session.scalars(select(StatusChange.person_id).where(StatusChange.kind == "signup"))
    )
    operator_or_appointed = set(
        session.scalars(
            select(StatusChange.person_id).where(StatusChange.kind.in_(["operator", "appoint"]))
        )
    )
    for person in people:
        assert person.id in signups | operator_or_appointed, person.status
        if person.status in ("searcher", "provider"):
            assert person.status_set_by_id is not None
        if person.status == "revoked":
            assert person.home_group_id is None and person.last_home_group_id is not None
    assert all(p.password_hash and verify_password(p.password_hash, PASSWORD) for p in people[:3])
    assert count(session, PersonUnavailability) >= 0


def test_the_named_cast_is_always_there(session: Session) -> None:
    rows = generate(session, PASSWORD, churches=2, groups_per_church=2, people=24)
    by_name = {r.name: r for r in rows}
    for role, name in CAST:
        assert name in by_name, role
    assert by_name["Olive Owner"].status == "owner"
    assert by_name["Ada Admin"].status == "admin"
    assert by_name["Rex Revoked"].status == "revoked"
    assert by_name["Ann Applicant"].status == "pending"
    assert by_name["Rex Revoked"].home_group is None


def test_the_same_seed_gives_the_same_people(engine: Engine) -> None:
    def run() -> list[CredentialRow]:
        connection = engine.connect()
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            return generate(db, PASSWORD, churches=2, groups_per_church=2, people=12)
        finally:
            db.close()
            transaction.rollback()
            connection.close()

    first, again = run(), run()
    assert [(r.email, r.status, r.church, r.home_group) for r in first] == [
        (r.email, r.status, r.church, r.home_group) for r in again
    ]


def test_generated_data_is_never_made_twice(session: Session) -> None:
    assert not has_generated(session)
    generate(session, PASSWORD, churches=2, groups_per_church=2, people=10)
    assert has_generated(session)
    with pytest.raises(DemoDataExists):
        generate(session, PASSWORD, churches=2, groups_per_church=2, people=10)
    assert count(session, Church) == 2  # nothing was added by the second call


def test_an_existing_owner_keeps_their_church(session: Session) -> None:
    from app.services.operators import create_first_owner

    create_first_owner(
        session,
        full_name="Real Owner",
        email="real.owner@example.com",
        mobile_number="+971500000042",
        password=secrets.token_urlsafe(16),
        church_name="Real Church",
        group_name="Real Group",
    )
    rows = generate(session, PASSWORD, churches=2, groups_per_church=2, people=20)
    check_rules(session)
    assert count(session, Church) == 2
    assert "Real Church" in {r.church for r in rows}
    assert "owner" not in [r.status for r in rows]  # the real OWNER is not copied
    owners = session.scalars(select(Person).where(Person.status == "owner")).all()
    assert [o.email for o in owners] == ["real.owner@example.com"]
