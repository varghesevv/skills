"""Succession of a home group's leader (docs/verification.md, "Succession").

Nobody stops leading a group without a successor appointed in the same transaction, or the group
closed in it (the leader being its only member). The successor must already belong to the group,
in any status from PENDING upwards; a PENDING, SEARCHER or PROVIDER successor becomes a VERIFIER
directly, without the usual vouches. A leader who steps down stays in the group as a PROVIDER (or a
SEARCHER), recorded as set by the verifier above them, and nobody they admitted is flagged. An
ADMIN or the OWNER who leads their own group hands it on and keeps their status.

The helpers here change the rows and add the history; the caller locks the people first (see
`locks.locked_in_scope`), checks the actor's authority and commits.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK
from app.models.trust import GroupInvitation, Notification, StatusChange
from app.services.locks import lock_people
from app.services.permissions import can_set_status
from app.services.status_history import last_change

LEADER_APPOINTED = "leader_appointed"  # notification kind: you now lead a home group
LEADER_STEPPED_DOWN = "leader_stepped_down"  # notification kind: you no longer lead a group
ADMIN_APPOINTED = "admin_appointed"  # notification kind: you are now the ADMIN of a church
ADMIN_STEPPED_DOWN = "admin_stepped_down"  # notification kind: you are no longer the ADMIN


def _history(person: Person, previous: str, actor: Person, kind: str, to: str) -> StatusChange:
    # The time is set here so changes made in one transaction still have an order.
    return StatusChange(
        person_id=person.id,
        from_status=previous,
        to_status=to,
        changed_by_id=actor.id,
        kind=kind,
        at=datetime.now(UTC),
    )


def other_members(db: Session, group: HomeGroup, leader_id: uuid.UUID) -> list[Person]:
    """The open, not revoked people who belong to the group, besides the leader."""
    return list(
        db.scalars(
            select(Person).where(
                Person.home_group_id == group.id,
                Person.id != leader_id,
                Person.closed_at.is_(None),
                Person.status != "revoked",
            )
        )
    )


def pick_successor(
    db: Session, group: HomeGroup, leader: Person, successor_id: uuid.UUID
) -> Person:
    """The member the leader hands the group to (already locked by the caller)."""
    successor = db.get(Person, successor_id)
    if (
        successor is None
        or successor.id == leader.id
        or successor.closed_at is not None
        or successor.status in ("revoked", "verifier")  # a VERIFIER leads a group of their own
        or successor.home_group_id != group.id
    ):
        raise ApiError(
            409, "successor_not_member", "The successor must be a member of the home group"
        )
    return successor


def revoke_invitations(db: Session, leader: Person, group: HomeGroup) -> None:
    """The group invitation links the leader gave stop working when they stop leading."""
    db.execute(
        update(GroupInvitation)
        .where(
            GroupInvitation.home_group_id == group.id,
            GroupInvitation.created_by_id == leader.id,
            GroupInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )


def appoint(db: Session, group: HomeGroup, successor: Person, actor: Person) -> None:
    """Make the member the group's leader: a VERIFIER, unless they hold a higher status."""
    if STATUS_RANK[successor.status] < STATUS_RANK["verifier"]:
        previous = successor.status
        successor.status = "verifier"
        successor.status_set_by_id = actor.id
        db.add(_history(successor, previous, actor, "appoint", "verifier"))
    group.leader_id = successor.id
    if successor.id != actor.id:
        db.add(Notification(person_id=successor.id, kind=LEADER_APPOINTED, subject_id=actor.id))


def stand_down(db: Session, leader: Person, actor: Person, to_status: str) -> None:
    """A VERIFIER who stops leading stays in the group as a PROVIDER or a SEARCHER, set by the
    leader above them. An ADMIN or the OWNER keep their status."""
    if leader.status != "verifier":
        return
    leader.status = to_status
    leader.status_set_by_id = actor.id
    db.add(_history(leader, "verifier", actor, "step-down", to_status))
    db.add(Notification(person_id=leader.id, kind=LEADER_STEPPED_DOWN, subject_id=actor.id))


def end_leadership(
    db: Session,
    group: HomeGroup,
    leader: Person,
    actor: Person,
    successor_id: uuid.UUID | None,
) -> Person | None:
    """The leader stops leading the group: the successor takes over, or the group closes when the
    leader is its only member. Returns the successor, or None when the group closed.

    The leader's own status is changed by the caller (a step-down, or a revocation).
    """
    if successor_id is not None:
        successor = pick_successor(db, group, leader, successor_id)
        revoke_invitations(db, leader, group)
        appoint(db, group, successor, actor)
        return successor
    if other_members(db, group, leader.id):
        raise ApiError(
            409, "successor_required", "Choose a successor from the members of the home group"
        )
    revoke_invitations(db, leader, group)
    group.closed_at = datetime.now(UTC)
    return None


def replace_leader(
    db: Session,
    actor: Person,
    group_id: uuid.UUID,
    successor_id: uuid.UUID,
    former_leader_status: str,
) -> HomeGroup:
    """An ADMIN (of the group's church) or the OWNER replaces the leader of a group, or hands on
    their own group, in one transaction. The commit is the caller's."""
    group = db.get(HomeGroup, group_id)
    if (
        group is None
        or group.closed_at is not None
        or (actor.status == "admin" and group.church_id != actor.church_id)
    ):
        raise ApiError(404, "not_found", "There is no such home group")
    people = lock_people(db, [actor.id, group.leader_id, successor_id])
    locked_actor = people.get(actor.id)
    # Read again from the locked rows: an ADMIN revoked or changed at this moment decides nothing.
    if (
        locked_actor is None
        or locked_actor.closed_at is not None
        or locked_actor.status not in ("admin", "owner")
    ):
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    # Locked after the people (the order of locks in services/locks.py).
    group = db.get(HomeGroup, group_id, with_for_update=True, populate_existing=True)
    leader = people.get(group.leader_id) if group is not None else None
    if group is None or group.closed_at is not None or leader is None:
        raise ApiError(409, "state_changed", "The home group changed meanwhile. Reload.")
    if leader.status == "verifier":
        if former_leader_status not in ("provider", "searcher"):
            raise ApiError(422, "invalid_choice", "A VERIFIER stays as a provider or a searcher")
        if not can_set_status(actor, leader, former_leader_status, last_change(db, leader)):
            raise ApiError(403, "status_not_allowed", "You may not make this change")
    else:  # an ADMIN or the OWNER who leads their own group hands it on
        if former_leader_status != "keep":
            raise ApiError(422, "invalid_choice", "An ADMIN or the OWNER keeps their status")
        if leader.id != actor.id:
            raise ApiError(403, "status_not_allowed", "You may not make this change")
    successor = pick_successor(db, group, leader, successor_id)
    if STATUS_RANK[successor.status] < STATUS_RANK["verifier"] and not can_set_status(
        actor, successor, "verifier", last_change(db, successor)
    ):
        raise ApiError(403, "status_not_allowed", "You may not make this change")
    revoke_invitations(db, leader, group)
    stand_down(db, leader, actor, former_leader_status)
    appoint(db, group, successor, actor)
    return group


def end_commit(db: Session) -> None:
    """Commit a succession. The database refuses a state that breaks a rule of the model (the
    deferred checks run here); nothing is half done."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "state_changed", "The home group changed meanwhile. Reload and try again."
        ) from None


def pick_church_successor(
    db: Session, church: Church, admin: Person, successor_id: uuid.UUID
) -> Person:
    """The member of the church who becomes its ADMIN (already locked by the caller)."""
    successor = db.get(Person, successor_id)
    if (
        successor is None
        or successor.id == admin.id
        or successor.closed_at is not None
        or successor.status in ("revoked", "admin", "owner")
        or successor.church_id != church.id
    ):
        raise ApiError(409, "successor_not_member", "The successor must be a member of the church")
    return successor


def hand_church_on(
    db: Session,
    church: Church,
    admin: Person,
    actor: Person,
    successor_id: uuid.UUID,
    group_successor_id: uuid.UUID | None,
    *,
    revoking: bool,
) -> bool:
    """The church's ADMIN stops being its ADMIN: the successor, a member of the church, becomes
    the ADMIN directly (if they lead a group they keep leading it), in the same transaction.

    If the old ADMIN leads a home group, it passes to `group_successor_id` (a member of it, who
    may be the new ADMIN). With no one to hand it to and other members in it, the call is refused;
    if the old ADMIN is its only member it closes when they are revoked, and when they only step
    down they keep leading it as a VERIFIER (the rule for a leader nobody can succeed). Returns
    whether the old ADMIN keeps leading their group. Their own status is the caller's to change.
    """
    successor = pick_church_successor(db, church, admin, successor_id)
    group = (
        db.get(HomeGroup, admin.home_group_id, with_for_update=True)
        if admin.home_group_id
        else None
    )
    leads = group is not None and group.closed_at is None and group.leader_id == admin.id
    if group_successor_id is not None:
        if not leads or group is None:
            raise ApiError(422, "invalid_choice", "There is no group to hand on")
        pick_successor(db, group, admin, group_successor_id)
    elif leads and group is not None and other_members(db, group, admin.id):
        raise ApiError(
            409, "successor_required", "Choose a successor from the members of their home group"
        )
    # Locked after the groups (the order of locks in services/locks.py).
    locked = db.get(Church, church.id, with_for_update=True, populate_existing=True)
    if locked is None or locked.closed_at is not None or locked.admin_id != admin.id:
        raise ApiError(409, "state_changed", "The church changed meanwhile. Reload.")
    # The new ADMIN first, so a group successor who is the new ADMIN gets no second promotion.
    previous = successor.status
    successor.status = "admin"
    successor.status_set_by_id = actor.id
    db.add(_history(successor, previous, actor, "appoint", "admin"))
    locked.admin_id = successor.id
    db.add(Notification(person_id=successor.id, kind=ADMIN_APPOINTED, subject_id=actor.id))
    keeps_group = False
    if leads and group is not None:
        if group_successor_id is not None:
            end_leadership(db, group, admin, actor, group_successor_id)
        elif revoking:
            end_leadership(db, group, admin, actor, None)  # alone: the group closes
        else:
            keeps_group = True
    return keeps_group


def replace_admin(
    db: Session,
    owner: Person,
    church_id: uuid.UUID,
    successor_id: uuid.UUID,
    former_admin_status: str,
    group_successor_id: uuid.UUID | None,
) -> tuple[Church, bool]:
    """The OWNER replaces the ADMIN of another church. The commit is the caller's. Returns the
    church and whether the old ADMIN keeps leading their group (as a VERIFIER)."""
    church = db.get(Church, church_id)
    if church is None or church.closed_at is not None:
        raise ApiError(404, "not_found", "There is no such church")
    admin_row = db.get(Person, church.admin_id)
    if admin_row is None:
        raise ApiError(409, "state_changed", "The church changed meanwhile. Reload.")
    if admin_row.status == "owner":
        # The OWNER is the ADMIN of their own church; that changes only by a handover (4.5).
        raise ApiError(
            409, "owner_church", "The OWNER's own church changes ADMIN by a handover of the OWNER"
        )
    ids = [
        owner.id,
        church.admin_id,
        successor_id,
        *([group_successor_id] if group_successor_id else []),
    ]
    people = lock_people(db, ids)
    locked_owner = people.get(owner.id)
    if locked_owner is None or locked_owner.closed_at is not None or locked_owner.status != "owner":
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    admin = people.get(church.admin_id)
    if admin is None or admin.status != "admin":
        raise ApiError(409, "state_changed", "The church changed meanwhile. Reload.")
    successor = people.get(successor_id)
    if (
        successor is not None
        and STATUS_RANK[successor.status] < STATUS_RANK["admin"]
        and successor.church_id == church.id
        and not can_set_status(owner, successor, "admin", last_change(db, successor))
    ):
        raise ApiError(403, "status_not_allowed", "You may not make this change")
    if not can_set_status(owner, admin, former_admin_status, last_change(db, admin)):
        raise ApiError(403, "status_not_allowed", "You may not make this change")
    keeps_group = hand_church_on(
        db, church, admin, owner, successor_id, group_successor_id, revoking=False
    )
    # The old ADMIN stays where they are: a PROVIDER or a SEARCHER, set by the OWNER, or a VERIFIER
    # when they keep leading a group nobody can take over.
    new_status = "verifier" if keeps_group else former_admin_status
    admin.status = new_status
    admin.status_set_by_id = owner.id
    db.add(_history(admin, "admin", owner, "step-down", new_status))
    db.add(Notification(person_id=admin.id, kind=ADMIN_STEPPED_DOWN, subject_id=owner.id))
    return church, keeps_group
