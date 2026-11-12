"""Who may do what in the church trust model.

Pure functions that mirror the permission checks in docs/verification.md (Data model summary).
They look at values only, never at the database, so every rule can be tested exhaustively. The
database constraints (migration 0007) are the last line of defence; these checks are the
first, and they give the clear answer to the caller.

Statuses are strings from `app.models.enums.STATUSES`, ordered by `STATUS_RANK`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.models.enums import STATUS_RANK


class PersonLike(Protocol):
    """The fields of a person the checks need; `app.models.Person` has them."""

    @property
    def id(self) -> UUID: ...
    @property
    def status(self) -> str: ...
    @property
    def church_id(self) -> UUID: ...
    @property
    def home_group_id(self) -> UUID | None: ...
    @property
    def last_home_group_id(self) -> UUID | None: ...
    @property
    def requested_status(self) -> str | None: ...
    @property
    def closed_at(self) -> datetime | None: ...


@dataclass(frozen=True)
class LastChange:
    """The latest status change of a target, and who made it.

    `changed_by_status` is the **current** status of the person who made the change (as in the
    reference code of docs/verification.md), or None when there was no person (an operator change
    in the database). A revocation or appointment with no person behind it cannot be overridden
    through the app.
    """

    kind: str
    changed_by_status: str | None


# The statuses each verifier may set. Setting VERIFIER or ADMIN only happens through approving a
# group request, a succession or an admin invitation, which keep the invariants; the permission
# check only says the actor is allowed to name that status.
_SETTABLE: dict[str, frozenset[str]] = {
    "owner": frozenset({"revoked", "pending", "searcher", "provider", "verifier", "admin"}),
    "admin": frozenset({"revoked", "pending", "searcher", "provider", "verifier"}),
    "verifier": frozenset({"revoked", "searcher", "provider"}),
}


def rank(status: str) -> int:
    return STATUS_RANK[status]


def is_verifier(person: PersonLike) -> bool:
    """A verifier is anyone who can change another person's status: VERIFIER or higher."""
    return person.closed_at is None and rank(person.status) >= rank("verifier")


def settable_statuses(actor: PersonLike) -> frozenset[str]:
    """The statuses `actor` may set on someone, before looking at the target."""
    if actor.closed_at is not None:
        return frozenset()
    return _SETTABLE.get(actor.status, frozenset())


def in_scope(actor: PersonLike, target: PersonLike) -> bool:
    """Whether `actor` has authority over `target`."""
    if actor.closed_at is not None:
        return False
    match actor.status:
        case "owner":
            return True
        case "admin":
            return target.church_id == actor.church_id
        case "verifier":
            # A revoked person is still in the scope of the group they were removed from.
            group = target.home_group_id or target.last_home_group_id
            return actor.home_group_id is not None and group == actor.home_group_id
        case _:
            return False


def can_set_status(
    actor: PersonLike,
    target: PersonLike,
    to: str,
    last_change: LastChange | None,
) -> bool:
    """Whether `actor` may change `target` to status `to`.

    `last_change` is the target's latest status change; callers must load it and pass None only
    when the target has no history. Forgetting it would let a leader override a higher
    verifier's revocation or appointment, so there is no default.

    This answers whether the actor has authority. A change to a VERIFIER or ADMIN target (or to
    VERIFIER or ADMIN) also needs a successor, a group or a church, and must go through the
    succession, group request, invitation or closing flow; the database constraints reject
    anything else.
    """
    if target.closed_at is not None:
        return False  # closed accounts cannot be changed
    if actor.id == target.id:
        return False  # nobody changes their own status (handover and closing a group are
        # separate operations)
    if target.status == "owner":
        return False  # only the platform operators change the OWNER
    if not in_scope(actor, target):
        return False
    if rank(target.status) >= rank(actor.status):
        return False  # only people below you
    if to not in settable_statuses(actor):
        return False
    # A revocation or leader appointment made by a higher verifier cannot be overridden.
    if last_change is None or last_change.kind not in ("revoke", "appoint"):
        return True
    if last_change.changed_by_status is None:
        return False  # made by the operators: not for the app to undo
    return rank(last_change.changed_by_status) <= rank(actor.status)


def can_admit(
    actor: PersonLike,
    applicant: PersonLike,
    to: str,
    live_vouch_voucher_ids: Iterable[UUID],
) -> bool:
    """Whether `actor` may admit `applicant` as `to` (searcher or provider).

    `live_vouch_voucher_ids` are the voucher ids of the applicant's live vouches (see
    `live_vouches`). The admitting verifier's own sign-off counts as the group leader's vouch.
    """
    if to not in ("searcher", "provider"):
        return False
    if applicant.closed_at is not None or actor.id == applicant.id:
        return False
    if not is_verifier(actor) or not in_scope(actor, applicant):
        return False
    if to == "searcher":
        return applicant.status == "pending"
    if applicant.status not in ("pending", "searcher"):
        return False
    # PROVIDER: at least one live vouch from someone other than the admitting verifier.
    return any(voucher_id != actor.id for voucher_id in live_vouch_voucher_ids)


def can_decline(actor: PersonLike, applicant: PersonLike) -> bool:
    """Whether `actor` may decline a pending application (closing it; nobody is revoked)."""
    return (
        applicant.closed_at is None
        and applicant.status == "pending"
        and actor.id != applicant.id
        and is_verifier(actor)
        and in_scope(actor, applicant)
    )


def can_vouch(voucher: PersonLike, applicant: PersonLike) -> bool:
    """Whether `voucher` may vouch for `applicant`: admitted, open, not themselves.

    Any admitted person in any church may vouch (docs/verification.md, "Joining"), so church and
    group are not compared.
    """
    if voucher.closed_at is not None or voucher.id == applicant.id:
        return False
    if rank(voucher.status) < rank("searcher"):
        return False
    if applicant.closed_at is not None:
        return False
    # A pending applicant, or a searcher who applies to become a provider.
    return applicant.status == "pending" or (
        applicant.status == "searcher" and applicant.requested_status == "provider"
    )


def live_vouches(
    vouches: Iterable[tuple[UUID, datetime | None]], vouchers: dict[UUID, PersonLike]
) -> list[UUID]:
    """Voucher ids of the vouches that count.

    A vouch counts when it is not withdrawn and its voucher is still an open, admitted person
    (not revoked, not closed). `vouches` are (voucher id, withdrawn_at) pairs; `vouchers` maps
    voucher ids to the people.
    """
    return [
        voucher_id
        for voucher_id, withdrawn_at in vouches
        if withdrawn_at is None
        and voucher_id in vouchers
        and vouchers[voucher_id].closed_at is None
        and rank(vouchers[voucher_id].status) >= rank("searcher")
    ]
