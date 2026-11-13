"""The permission rules of the church trust model, checked exhaustively.

The expected answers are written out here from docs/verification.md ("Who can change whose
status" and the permission check), not computed with the code under test.
"""

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.models.enums import STATUSES
from app.services.permissions import (
    LastChange,
    can_admit,
    can_decline,
    can_decline_upgrade,
    can_set_status,
    can_vouch,
    in_scope,
    is_verifier,
    live_vouches,
    settable_statuses,
)

CHURCH_A = uuid.uuid4()
CHURCH_B = uuid.uuid4()
GROUP_A1 = uuid.uuid4()
GROUP_A2 = uuid.uuid4()
GROUP_B1 = uuid.uuid4()


@dataclass
class P:
    status: str
    church_id: uuid.UUID = CHURCH_A
    home_group_id: uuid.UUID | None = GROUP_A1
    last_home_group_id: uuid.UUID | None = None
    requested_status: str | None = None
    closed_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


def person(status: str, **extra: object) -> P:
    if status == "revoked" and "home_group_id" not in extra:
        extra = {"home_group_id": None, "last_home_group_id": GROUP_A1, **extra}
    return P(status, **extra)  # type: ignore[arg-type]


# What each verifier may set, and on whom (docs/verification.md, "Who can change whose status").
EXPECTED_SETTABLE = {
    "owner": {"revoked", "pending", "searcher", "provider", "verifier", "admin"},
    "admin": {"revoked", "pending", "searcher", "provider", "verifier"},
    "verifier": {"revoked", "searcher", "provider"},
}
# Statuses of people below each verifier (and so changeable by them).
BELOW = {
    "owner": {"revoked", "pending", "searcher", "provider", "verifier", "admin"},
    "admin": {"revoked", "pending", "searcher", "provider", "verifier"},
    "verifier": {"revoked", "pending", "searcher", "provider"},
}


# ---- the matrix: every actor status against every target status and every new status ------------


@pytest.mark.parametrize(
    ("actor_status", "target_status", "to"), itertools.product(STATUSES, STATUSES, STATUSES)
)
def test_can_set_status_matrix(actor_status: str, target_status: str, to: str) -> None:
    """The target is always in the actor's scope (same group), so only the rules of status count."""
    actor = person(actor_status)
    target = person(target_status)
    expected = (
        actor_status in EXPECTED_SETTABLE
        and target_status in BELOW[actor_status]
        and to in EXPECTED_SETTABLE[actor_status]
    )
    assert can_set_status(actor, target, to, None) is expected


def test_nobody_below_verifier_can_set_anything() -> None:
    for status in ("revoked", "pending", "searcher", "provider"):
        assert settable_statuses(person(status)) == frozenset()


def test_settable_statuses_match_the_rules() -> None:
    for status, expected in EXPECTED_SETTABLE.items():
        assert settable_statuses(person(status)) == expected


# ---- scope ---------------------------------------------------------------------------------


def test_owner_has_scope_over_everyone() -> None:
    owner = person("owner")
    assert in_scope(owner, person("pending", church_id=CHURCH_B, home_group_id=GROUP_B1))


def test_admin_scope_is_their_church() -> None:
    admin = person("admin")
    assert in_scope(admin, person("provider", home_group_id=GROUP_A2))
    assert not in_scope(admin, person("provider", church_id=CHURCH_B, home_group_id=GROUP_B1))


def test_verifier_scope_is_their_group() -> None:
    leader = person("verifier")
    assert in_scope(leader, person("pending"))
    assert not in_scope(leader, person("pending", home_group_id=GROUP_A2))
    assert not in_scope(leader, person("pending", church_id=CHURCH_B, home_group_id=GROUP_B1))


def test_verifier_scope_includes_people_revoked_from_their_group() -> None:
    leader = person("verifier")
    assert in_scope(leader, person("revoked"))  # last group is theirs
    assert not in_scope(leader, person("revoked", last_home_group_id=GROUP_A2))


def test_lower_statuses_have_no_scope() -> None:
    for status in ("revoked", "pending", "searcher", "provider"):
        assert not in_scope(person(status), person("pending"))


def test_a_closed_actor_has_no_scope_and_no_rights() -> None:
    closed = person("admin", closed_at=datetime.now(UTC))
    target = person("provider")
    assert not in_scope(closed, target)
    assert not can_set_status(closed, target, "revoked", None)
    assert settable_statuses(closed) == frozenset()
    assert not is_verifier(closed)


# ---- the rules around the matrix ---------------------------------------------------------------


def test_nobody_changes_their_own_status() -> None:
    admin = person("admin")
    assert not can_set_status(admin, admin, "provider", None)


def test_the_owner_status_can_never_be_changed_through_the_app() -> None:
    owner = person("owner")
    other_owner_like = person("owner", id=uuid.uuid4())
    assert not can_set_status(owner, other_owner_like, "provider", None)
    assert not can_set_status(person("admin"), other_owner_like, "revoked", None)


def test_out_of_scope_targets_cannot_be_changed() -> None:
    leader = person("verifier")
    assert not can_set_status(leader, person("provider", home_group_id=GROUP_A2), "revoked", None)
    admin = person("admin")
    assert not can_set_status(
        admin, person("provider", church_id=CHURCH_B, home_group_id=GROUP_B1), "revoked", None
    )


def test_closed_targets_cannot_be_changed() -> None:
    target = person("searcher", closed_at=datetime.now(UTC))
    assert not can_set_status(person("owner"), target, "provider", None)


@pytest.mark.parametrize("kind", ["revoke", "appoint"])
def test_a_higher_verifiers_revocation_or_appointment_cannot_be_overridden(kind: str) -> None:
    target = person("revoked") if kind == "revoke" else person("provider")
    leader = person("verifier")
    admin = person("admin")
    change = LastChange(kind=kind, changed_by_status="admin")
    assert not can_set_status(leader, target, "searcher", change)
    # The ADMIN who made it, or a higher one, can.
    assert can_set_status(admin, target, "searcher", change)
    assert can_set_status(person("owner"), target, "searcher", change)


@pytest.mark.parametrize("kind", ["admit", "reinstate", "reconfirm", "step-down", "signup"])
def test_ordinary_changes_can_be_changed_by_any_verifier_with_authority(kind: str) -> None:
    leader = person("verifier")
    target = person("provider")
    assert can_set_status(leader, target, "searcher", LastChange(kind, "admin"))


def test_a_verifier_can_reinstate_someone_they_revoked() -> None:
    leader = person("verifier")
    revoked = person("revoked")
    change = LastChange(kind="revoke", changed_by_status="verifier")
    assert can_set_status(leader, revoked, "searcher", change)


# ---- admission ---------------------------------------------------------------------------------


def test_leader_admits_a_pending_applicant_as_searcher_without_other_vouches() -> None:
    assert can_admit(person("verifier"), person("pending"), "searcher", [])


def test_a_searcher_cannot_be_admitted_as_searcher_again() -> None:
    assert not can_admit(person("verifier"), person("searcher"), "searcher", [])


def test_provider_needs_a_vouch_from_someone_other_than_the_admitting_verifier() -> None:
    leader = person("verifier")
    applicant = person("pending")
    other = uuid.uuid4()
    assert not can_admit(leader, applicant, "provider", [])
    assert not can_admit(leader, applicant, "provider", [leader.id])
    assert can_admit(leader, applicant, "provider", [other])
    assert can_admit(leader, applicant, "provider", [leader.id, other])


def test_a_searcher_can_be_admitted_as_provider() -> None:
    assert can_admit(person("verifier"), person("searcher"), "provider", [uuid.uuid4()])


@pytest.mark.parametrize("status", ["provider", "verifier", "admin", "owner", "revoked"])
def test_only_pending_and_searchers_are_admitted_as_provider(status: str) -> None:
    assert not can_admit(person("owner"), person(status), "provider", [uuid.uuid4()])


@pytest.mark.parametrize("to", ["pending", "verifier", "admin", "revoked", "owner"])
def test_admission_is_only_to_searcher_or_provider(to: str) -> None:
    assert not can_admit(person("owner"), person("pending"), to, [uuid.uuid4()])


@pytest.mark.parametrize("actor_status", ["revoked", "pending", "searcher", "provider"])
def test_only_verifiers_admit(actor_status: str) -> None:
    assert not can_admit(person(actor_status), person("pending"), "searcher", [])


def test_admission_needs_scope() -> None:
    leader = person("verifier")
    outsider = person("pending", home_group_id=GROUP_A2)
    assert not can_admit(leader, outsider, "searcher", [])
    assert can_admit(person("admin"), outsider, "searcher", [])  # ADMIN covers the church
    assert not can_admit(
        person("admin"),
        person("pending", church_id=CHURCH_B, home_group_id=GROUP_B1),
        "searcher",
        [],
    )


def test_nobody_admits_themselves_and_closed_applications_stay_closed() -> None:
    admin = person("admin")
    assert not can_admit(admin, admin, "searcher", [])
    assert not can_admit(
        person("owner"), person("pending", closed_at=datetime.now(UTC)), "searcher", []
    )


def test_decline_follows_the_same_authority() -> None:
    assert can_decline(person("verifier"), person("pending"))
    assert not can_decline(person("verifier"), person("pending", home_group_id=GROUP_A2))
    assert not can_decline(person("verifier"), person("searcher"))
    assert not can_decline(person("searcher"), person("pending"))
    assert not can_decline(person("admin"), person("admin"))


# ---- vouching ----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", STATUSES)
def test_who_can_vouch(status: str) -> None:
    applicant = person("pending")
    assert can_vouch(person(status), applicant) is (status not in ("revoked", "pending"))


def test_nobody_vouches_for_themselves_or_for_closed_accounts() -> None:
    searcher = person("searcher")
    assert not can_vouch(searcher, searcher)
    assert not can_vouch(searcher, person("pending", closed_at=datetime.now(UTC)))
    assert not can_vouch(person("searcher", closed_at=datetime.now(UTC)), person("pending"))


def test_vouching_is_for_pending_applicants_or_searchers_applying_to_provide() -> None:
    voucher = person("provider")
    assert can_vouch(voucher, person("pending"))
    assert can_vouch(voucher, person("searcher", requested_status="provider"))
    assert not can_vouch(voucher, person("searcher"))
    assert not can_vouch(voucher, person("provider"))
    assert not can_vouch(voucher, person("revoked"))


def test_live_vouches_skip_withdrawn_revoked_pending_and_closed_vouchers() -> None:
    people = {
        "good": person("searcher"),
        "withdrawn": person("provider"),
        "revoked": person("revoked"),
        "pending": person("pending"),
        "closed": person("searcher", closed_at=datetime.now(UTC)),
        "other_church": person("provider", church_id=CHURCH_B, home_group_id=GROUP_B1),
    }
    vouches = [(p.id, None) for name, p in people.items() if name != "withdrawn"]
    vouches.append((people["withdrawn"].id, datetime.now(UTC)))
    live = live_vouches(vouches, {p.id: p for p in people.values()})
    # Any admitted person in any church counts.
    assert set(live) == {people["good"].id, people["other_church"].id}


def test_a_voucher_from_another_church_counts_toward_provider_admission() -> None:
    outsider = person("searcher", church_id=CHURCH_B, home_group_id=GROUP_B1)
    leader = person("verifier")
    assert can_vouch(outsider, person("pending"))
    assert can_admit(leader, person("pending"), "provider", [outsider.id])


@pytest.mark.parametrize("kind", ["revoke", "appoint"])
def test_a_change_made_by_the_operators_is_not_overridden_through_the_app(kind: str) -> None:
    change = LastChange(kind=kind, changed_by_status=None)
    target = person("revoked") if kind == "revoke" else person("provider")
    assert not can_set_status(person("admin"), target, "searcher", change)
    assert not can_set_status(person("owner"), target, "searcher", change)


# ---- declining a searcher's request to become a provider ----------------------------------------


def test_a_request_to_become_a_provider_can_be_declined_only_in_scope_by_a_leader() -> None:
    asking = person("searcher", requested_status="provider")
    leader = person("verifier")
    assert can_decline_upgrade(leader, asking)
    assert not can_decline_upgrade(leader, person("searcher"))  # no request
    assert not can_decline_upgrade(leader, person("pending", requested_status="provider"))
    assert not can_decline_upgrade(leader, person("provider", requested_status="provider"))
    assert not can_decline_upgrade(
        leader, person("searcher", requested_status="provider", closed_at=datetime.now(UTC))
    )
    assert not can_decline_upgrade(asking, asking)  # nobody declines themselves
    assert not can_decline_upgrade(
        person("verifier", home_group_id=GROUP_A2), asking
    )  # out of scope
    assert not can_decline_upgrade(person("provider"), asking)  # not a leader
    assert can_decline_upgrade(person("admin"), asking)  # the church's ADMIN
    assert not can_decline_upgrade(
        person("admin", church_id=CHURCH_B, home_group_id=GROUP_B1), asking
    )
    assert can_decline_upgrade(person("owner", church_id=CHURCH_B, home_group_id=GROUP_B1), asking)
