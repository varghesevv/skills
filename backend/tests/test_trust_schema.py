"""One test per rule of the church trust model, against the real database constraints.

Rule numbers are those of docs/verification.md (Data model summary). These tests protect the
model even if application code has a bug.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AdminInvitation,
    Church,
    ContactView,
    GroupRequest,
    HandoverRequest,
    HomeGroup,
    MoveRequest,
    Person,
    StatusChange,
    Vouch,
)
from tests.trust_helpers import World, check_rules, make_person, now

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


# ---- rule 1: exactly one OWNER ----------------------------------------------------------


def test_second_open_owner_is_rejected(world: World) -> None:
    other = world.add_person("owner")
    world.session.add(other)
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_owner_cannot_be_demoted_without_a_replacement(world: World) -> None:
    world.owner.status = "admin"
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_owner_must_be_admin_of_their_own_church(world: World) -> None:
    world.church.admin_id = world.add_person("admin").id
    with pytest.raises(IntegrityError):
        check_rules(world.session)


# ---- rule 2: every open, non-revoked person is in a group of their own church ---------------


def test_open_person_needs_a_home_group(world: World) -> None:
    world.session.add(make_person(world.church, None, "pending"))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_revoked_person_has_no_home_group(world: World) -> None:
    person = make_person(world.church, world.group, "pending")
    person.status = "revoked"
    person.home_group_id = world.group.id
    world.session.add(person)
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_home_group_must_belong_to_the_persons_church(world: World) -> None:
    _church, other_group, _admin = world.add_church()
    world.session.add(make_person(world.church, other_group, "pending"))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_closed_account_has_no_group_and_no_details(world: World) -> None:
    person = world.add_person("searcher")
    person.closed_at = now()
    with pytest.raises(IntegrityError):  # still has a group and details
        world.session.flush()


def test_closing_clears_details_and_group(world: World) -> None:
    person = world.add_person("searcher")
    person.closed_at = now()
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    check_rules(world.session)


def test_open_account_needs_its_details(world: World) -> None:
    world.session.add(make_person(world.church, world.group, "pending", email=None))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_email_is_unique_among_open_accounts_and_free_after_closing(world: World) -> None:
    first = world.add_person("searcher", email="same@example.com")
    clash = make_person(world.church, world.group, "pending", email="same@example.com")
    world.session.add(clash)
    with pytest.raises(IntegrityError):
        world.session.flush()
    world.session.rollback()

    # A closed account does not hold the address.
    world2 = World(world.session)
    gone = world2.add_person("searcher", email="again@example.com")
    gone.closed_at = now()
    gone.home_group_id = None
    gone.full_name = gone.email = gone.mobile_number = gone.password_hash = None
    world2.session.flush()
    world2.session.add(
        make_person(world2.church, world2.group, "pending", email="again@example.com")
    )
    world2.session.flush()
    assert first is not None


def test_revoked_accounts_still_hold_their_email(world: World) -> None:
    person = world.add_person("searcher", email="revoked@example.com")
    person.status = "revoked"
    person.home_group_id = None
    world.session.flush()
    world.session.add(
        make_person(world.church, world.group, "pending", email="revoked@example.com")
    )
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_mobile_number_is_unique_among_open_accounts(world: World) -> None:
    world.add_person("searcher", mobile_number="+971500000099")
    world.session.add(
        make_person(world.church, world.group, "pending", mobile_number="+971500000099")
    )
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_uppercase_email_is_rejected(world: World) -> None:
    world.session.add(make_person(world.church, world.group, "pending", email="Mixed@Example.com"))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_unknown_status_is_rejected(world: World) -> None:
    world.session.add(make_person(world.church, world.group, "king"))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_rate_needs_a_currency(world: World) -> None:
    world.session.add(make_person(world.church, world.group, "provider", rate_per_hour=20))
    with pytest.raises(IntegrityError):
        world.session.flush()


# ---- rule 3: one ADMIN per open church --------------------------------------------------


def test_second_admin_in_a_church_is_rejected(world: World) -> None:
    church, _group, _admin = world.add_church()
    extra_group = HomeGroup(
        id=uuid.uuid4(), church_id=church.id, name="Extra", leader_id=uuid.uuid4()
    )
    del extra_group  # the second ADMIN joins the church's existing group instead
    other = make_person(church, _group, "admin")
    world.session.add(other)
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_church_needs_an_open_admin_of_its_own(world: World) -> None:
    church, _group, _admin = world.add_church()
    church.admin_id = world.owner.id  # the OWNER belongs to another church
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_church_cannot_lose_its_admin_without_a_replacement(world: World) -> None:
    _church, _group, admin = world.add_church()
    admin.status = "provider"
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_admin_is_replaced_in_one_transaction(world: World) -> None:
    church, group, admin = world.add_church()
    successor = make_person(church, group, "provider")
    world.session.add(successor)
    world.session.flush()
    admin.status = "provider"
    successor.status = "admin"
    church.admin_id = successor.id
    group.leader_id = successor.id  # the old ADMIN led the group, so the successor leads it
    check_rules(world.session)


def test_church_names_are_unique_while_open(world: World) -> None:
    world.add_church("Grace")
    other_admin = uuid.uuid4()
    world.session.add(Church(id=uuid.uuid4(), name="GRACE", admin_id=other_admin))
    with pytest.raises(IntegrityError):
        world.session.flush()


# ---- rule 4: one leader per open home group, who belongs to it ------------------------------


def test_group_leader_must_belong_to_the_group(world: World) -> None:
    _church, _group, stranger_admin = world.add_church()
    world.group.leader_id = stranger_admin.id
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_group_leader_needs_status_verifier_or_higher(world: World) -> None:
    member = world.add_person("provider")
    world.group.leader_id = member.id
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_a_person_leads_at_most_one_open_group(world: World) -> None:
    second = HomeGroup(
        id=uuid.uuid4(), church_id=world.church.id, name="Second", leader_id=world.owner.id
    )
    world.session.add(second)
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_a_closed_group_does_not_block_its_leader_from_leading_again(world: World) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Short lived")
    check_rules(world.session)
    # The group is closed and its leader moves back to the first group as a provider.
    group.closed_at = now()
    leader.status = "provider"
    leader.home_group_id = world.group.id
    check_rules(world.session)
    # The closed group still names its last leader, who can now lead a new group.
    world.add_group(leader, "Second time")
    check_rules(world.session)


def test_group_names_are_unique_per_church_while_open(world: World) -> None:
    leader = world.add_person("verifier")
    world.add_group(leader, "Alpha")
    other = world.add_person("verifier")
    with pytest.raises(IntegrityError):
        world.add_group(other, "ALPHA")


# ---- rule 5: every VERIFIER leads their own group ---------------------------------------


def test_verifier_must_lead_their_group(world: World) -> None:
    world.add_person("verifier")  # in the first group, which the OWNER leads
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_verifier_who_leads_their_group_is_accepted(world: World) -> None:
    leader = world.add_person("provider")
    world.add_group(leader, "New group")
    check_rules(world.session)


# ---- rule 6: succession in the same transaction -----------------------------------------------


def test_leader_cannot_step_down_without_a_successor(world: World) -> None:
    leader = world.add_person("provider")
    world.add_group(leader, "Led")
    leader.status = "verifier"
    check_rules(world.session)
    leader.status = "provider"
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_leader_steps_down_when_a_successor_is_named_in_the_same_transaction(
    world: World,
) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Led")
    leader.status = "verifier"
    member = world.add_person("provider", group)
    check_rules(world.session)
    leader.status = "provider"
    member.status = "verifier"
    group.leader_id = member.id
    check_rules(world.session)


def test_leader_cannot_leave_by_closing_the_account(world: World) -> None:
    leader = world.add_person("provider")
    world.add_group(leader, "Led")
    leader.status = "verifier"
    check_rules(world.session)
    leader.closed_at = now()
    leader.home_group_id = None
    leader.full_name = leader.email = leader.mobile_number = leader.password_hash = None
    with pytest.raises(IntegrityError):
        check_rules(world.session)


def test_group_can_be_closed_together_with_its_leader_leaving(world: World) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Led")
    leader.status = "verifier"
    check_rules(world.session)
    group.closed_at = now()
    leader.status = "provider"
    leader.home_group_id = world.group.id
    check_rules(world.session)


# ---- history, vouches and records -----------------------------------------------------------


def test_status_history_is_append_only(world: World) -> None:
    member = world.add_person("searcher")
    change = StatusChange(
        person_id=member.id,
        from_status="pending",
        to_status="searcher",
        changed_by_id=world.owner.id,
        kind="admit",
    )
    world.session.add(change)
    world.session.flush()
    change.to_status = "provider"
    with pytest.raises(DBAPIError):
        world.session.flush()


def test_history_rows_cannot_be_deleted(world: World) -> None:
    member = world.add_person("searcher")
    change = StatusChange(person_id=member.id, from_status=None, to_status="pending", kind="signup")
    world.session.add(change)
    world.session.flush()
    world.session.delete(change)
    with pytest.raises(DBAPIError):
        world.session.flush()


@pytest.mark.parametrize(
    ("kind", "has_actor", "own_change"),
    [
        ("admit", False, False),  # needs an actor
        ("signup", True, False),  # signup has none
        ("operator", True, False),
        ("admit", True, True),  # nobody changes their own status
    ],
)
def test_history_actor_rules(world: World, kind: str, has_actor: bool, own_change: bool) -> None:
    member = world.add_person("searcher")
    actor = None
    if has_actor:
        actor = member.id if own_change else world.owner.id
    elif own_change:
        actor = member.id
    world.session.add(
        StatusChange(
            person_id=member.id,
            from_status="pending",
            to_status="searcher",
            changed_by_id=actor,
            kind=kind,
        )
    )
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_owner_may_change_their_own_status_in_a_handover(world: World) -> None:
    world.session.add(
        StatusChange(
            person_id=world.owner.id,
            from_status="owner",
            to_status="provider",
            changed_by_id=world.owner.id,
            kind="handover",
        )
    )
    world.session.flush()


def test_a_vouch_is_for_a_pending_applicant(world: World) -> None:
    applicant = world.add_person("pending")
    voucher = world.add_person("searcher")
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=voucher.id))
    world.session.flush()


def test_nobody_vouches_for_themselves(world: World) -> None:
    applicant = world.add_person("pending")
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=applicant.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_a_pending_person_cannot_vouch(world: World) -> None:
    applicant = world.add_person("pending")
    other = world.add_person("pending")
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=other.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_a_revoked_person_cannot_vouch(world: World) -> None:
    applicant = world.add_person("pending")
    revoked = world.add_person("searcher")
    revoked.status = "revoked"
    revoked.home_group_id = None
    world.session.flush()
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=revoked.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_one_vouch_per_voucher_and_applicant(world: World) -> None:
    applicant = world.add_person("pending")
    voucher = world.add_person("searcher")
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=voucher.id))
    world.session.flush()
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=voucher.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_a_searcher_applying_to_provide_can_collect_vouches(world: World) -> None:
    applicant = world.add_person("searcher", requested_status="provider")
    voucher = world.add_person("provider")
    world.session.add(Vouch(applicant_id=applicant.id, voucher_id=voucher.id))
    world.session.flush()


def test_a_searcher_who_is_not_applying_cannot_collect_vouches(world: World) -> None:
    searcher = world.add_person("searcher")
    voucher = world.add_person("provider")
    world.session.add(Vouch(applicant_id=searcher.id, voucher_id=voucher.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_contact_view_stores_who_looked_not_the_number(world: World) -> None:
    member = world.add_person("searcher")
    world.session.add(ContactView(viewer_id=world.owner.id, person_id=member.id, screen="person"))
    world.session.flush()
    columns = {column.name for column in ContactView.__table__.columns}
    assert not {"mobile_number", "number", "phone"} & columns


def test_deleting_is_not_how_people_leave(world: World) -> None:
    """Rows of people are kept; see the closing tests above."""
    person = world.add_person("searcher")
    assert world.session.scalars(select(Person).where(Person.id == person.id)).one() is person


# ---- requests, invitations and references stay inside one church --------------------------


def test_revoked_persons_last_group_must_be_in_their_church(world: World) -> None:
    _church, other_group, _admin = world.add_church()
    person = world.add_person("searcher")
    person.status = "revoked"
    person.home_group_id = None
    person.last_home_group_id = other_group.id
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_revoked_person_keeps_the_group_they_were_removed_from(world: World) -> None:
    person = world.add_person("searcher")
    person.status = "revoked"
    person.home_group_id = None
    person.last_home_group_id = world.group.id
    check_rules(world.session)


def test_a_move_stays_within_one_church(world: World) -> None:
    _church, other_group, _admin = world.add_church()
    member = world.add_person("searcher")
    world.session.add(
        MoveRequest(person_id=member.id, from_group_id=world.group.id, to_group_id=other_group.id)
    )
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_a_move_between_groups_of_one_church_is_accepted(world: World) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Target")
    member = world.add_person("searcher")
    world.session.add(
        MoveRequest(person_id=member.id, from_group_id=world.group.id, to_group_id=group.id)
    )
    world.session.flush()


@pytest.mark.parametrize(
    "state, decided",
    [("open", True), ("approved", False), ("declined", False)],
)
def test_group_request_decision_matches_state(world: World, state: str, decided: bool) -> None:
    member = world.add_person("searcher")
    values: dict[str, object] = {
        "requester_id": member.id,
        "church_id": world.church.id,
        "group_name": "New",
        "state": state,
    }
    if decided:
        values.update(decided_by_id=world.owner.id, decided_at=now())
    world.session.add(GroupRequest(**values))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_group_request_decided_by_the_admin_is_accepted(world: World) -> None:
    member = world.add_person("searcher")
    world.session.add(
        GroupRequest(
            requester_id=member.id,
            church_id=world.church.id,
            group_name="New",
            state="approved",
            decided_by_id=world.owner.id,
            decided_at=now(),
        )
    )
    world.session.flush()


def _admin_invitation(world: World, **extra: object) -> AdminInvitation:
    values: dict[str, object] = {
        "email": "invitee@example.com",
        "church_name": "Third church",
        "invited_by_id": world.owner.id,
        "token_hash": uuid.uuid4().hex,
        "expires_at": now(),
    }
    values.update(extra)
    return AdminInvitation(**values)


def test_invitation_has_one_outcome(world: World) -> None:
    world.session.add(_admin_invitation(world, email=None, accepted_at=now(), cancelled_at=now()))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_invitation_email_is_cleared_once_decided(world: World) -> None:
    world.session.add(_admin_invitation(world, accepted_at=now()))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_open_invitation_keeps_the_email_and_decided_one_does_not(world: World) -> None:
    world.session.add(_admin_invitation(world))
    world.session.add(_admin_invitation(world, email=None, accepted_at=now()))
    world.session.flush()


def test_handover_has_one_outcome(world: World) -> None:
    _church, _group, admin = world.add_church()
    world.session.add(
        HandoverRequest(
            owner_id=world.owner.id,
            new_owner_id=admin.id,
            accepted_at=now(),
            cancelled_at=now(),
        )
    )
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_only_one_handover_is_open_at_a_time(world: World) -> None:
    _church, _group, admin = world.add_church()
    world.session.add(HandoverRequest(owner_id=world.owner.id, new_owner_id=admin.id))
    world.session.flush()
    world.session.add(HandoverRequest(owner_id=world.owner.id, new_owner_id=admin.id))
    with pytest.raises(IntegrityError):
        world.session.flush()


def test_move_has_one_outcome(world: World) -> None:
    leader = world.add_person("provider")
    group = world.add_group(leader, "Target")
    member = world.add_person("searcher")
    world.session.add(
        MoveRequest(
            person_id=member.id,
            from_group_id=world.group.id,
            to_group_id=group.id,
            completed_at=now(),
            cancelled_at=now(),
        )
    )
    with pytest.raises(IntegrityError):
        world.session.flush()
