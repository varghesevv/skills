"""Closing a home group (docs/verification.md, "Closing home groups and churches").

A group closes only once its leader is its last member. The leader closes it by moving themselves
into another open home group of the church, in the same transaction: they leave the group, the group
is closed (kept, with the date) and they join the other one. A VERIFIER no longer leads a group, so
they become a PROVIDER or a SEARCHER, recorded as set by the church's ADMIN; an ADMIN or the OWNER
keeps their status.

Only the OWNER closes a church, and not their own: the church, all its home groups and all its
members' accounts are closed together (the rows are kept, with the date, for the history), and
nobody is revoked or flagged. The church's revoked people stay as they are, so they still cannot
sign up again.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.trust import (
    GroupInvitation,
    GroupRequest,
    MoveRequest,
    Notification,
    StatusChange,
)
from app.services import account_closing, succession
from app.services.locks import lock_people
from app.services.moves import MEMBER_MOVED_IN, MOVE_CANCELLED
from app.services.succession import end_commit

GROUP_CLOSED = "group_closed"  # notification kind: a home group of your church was closed


def close_group(
    db: Session,
    leader: Person,
    group_id: uuid.UUID,
    move_to_group_id: uuid.UUID,
    former_leader_status: str,
) -> tuple[HomeGroup, HomeGroup]:
    """The leader closes their own group and moves into `move_to_group_id`. The commit is the
    caller's. Returns the closed group and the group they joined."""
    group = db.get(HomeGroup, group_id)
    church = db.get(Church, group.church_id) if group is not None else None
    if group is None or church is None or group.closed_at is not None:
        raise ApiError(404, "not_found", "There is no such home group")
    people = lock_people(db, [leader.id, church.admin_id])
    me = people.get(leader.id)
    # The leader of the group, as read from the locked rows: anyone else gets the same `404`.
    if (
        me is None
        or me.closed_at is not None
        or group.leader_id != me.id
        or me.home_group_id != group.id
    ):
        raise ApiError(404, "not_found", "There is no such home group")
    # Both groups, locked in id order (so two leaders closing into each other's groups cannot wait
    # for each other): the closing one for update, the joined one for sharing (see signup).
    ordered = sorted({group.id, move_to_group_id}, key=str)
    locked: dict[uuid.UUID, HomeGroup | None] = {}
    for gid in ordered:
        locked[gid] = (
            db.get(HomeGroup, gid, with_for_update=True, populate_existing=True)
            if gid == group.id
            else db.get(HomeGroup, gid, with_for_update={"read": True}, populate_existing=True)
        )
    closing, target = locked[group.id], locked.get(move_to_group_id)
    if closing is None or closing.closed_at is not None or closing.leader_id != me.id:
        raise ApiError(409, "state_changed", "The home group changed meanwhile. Reload.")
    if (
        target is None
        or target.id == closing.id
        or target.closed_at is not None
        or target.church_id != closing.church_id
    ):
        raise ApiError(422, "invalid_choice", "That home group is not available")
    if succession.other_members(db, closing, me.id):
        raise ApiError(409, "group_not_empty", "A group closes when its leader is its last member")
    if me.status == "verifier":
        if former_leader_status not in ("provider", "searcher"):
            raise ApiError(422, "invalid_choice", "A VERIFIER stays as a provider or a searcher")
    elif former_leader_status != "keep":
        raise ApiError(422, "invalid_choice", "An ADMIN or the OWNER keeps their status")
    now = datetime.now(UTC)
    # Links to the group stop working, and moves into it end.
    db.execute(
        update(GroupInvitation)
        .where(GroupInvitation.home_group_id == closing.id, GroupInvitation.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    for move in db.scalars(
        select(MoveRequest).where(
            MoveRequest.completed_at.is_(None),
            MoveRequest.cancelled_at.is_(None),
            (MoveRequest.from_group_id == closing.id) | (MoveRequest.to_group_id == closing.id),
        )
    ):
        move.cancelled_at = now
        if move.person_id != me.id:
            db.add(Notification(person_id=move.person_id, kind=MOVE_CANCELLED, subject_id=me.id))
    if me.status == "verifier":
        # Recorded as set by the church's ADMIN, even though the leader asked: the chain of trust
        # stays unbroken (a person never sets their own status).
        me.status = former_leader_status
        me.status_set_by_id = church.admin_id
        db.add(
            StatusChange(
                person_id=me.id,
                from_status="verifier",
                to_status=former_leader_status,
                changed_by_id=church.admin_id,
                kind="step-down",
                at=now,
            )
        )
    closing.closed_at = now
    me.home_group_id = target.id
    if target.leader_id != me.id:
        db.add(Notification(person_id=target.leader_id, kind=MEMBER_MOVED_IN, subject_id=me.id))
    if church.admin_id != me.id:
        db.add(Notification(person_id=church.admin_id, kind=GROUP_CLOSED, subject_id=me.id))
    return closing, target


def commit(db: Session) -> None:
    end_commit(db)


def close_church(db: Session, owner: Person, church_id: uuid.UUID) -> tuple[Church, int, int]:
    """The OWNER closes another church. The commit is the caller's. Returns the church, how many
    home groups and how many accounts were closed."""
    church = db.get(Church, church_id)
    if church is None or church.closed_at is not None:
        raise ApiError(404, "not_found", "There is no such church")
    admin = db.get(Person, church.admin_id)
    if admin is None or admin.status == "owner":
        raise ApiError(
            409, "owner_church", "The OWNER's own church is not closed: hand over the role first"
        )
    # The open members (not the revoked, who stay on the church's list, nor the closed).
    member_ids = list(
        db.scalars(
            select(Person.id).where(
                Person.church_id == church.id,
                Person.closed_at.is_(None),
                Person.status != "revoked",
            )
        )
    )
    people = lock_people(db, [owner.id, *member_ids])
    locked_owner = people.get(owner.id)
    if locked_owner is None or locked_owner.closed_at is not None or locked_owner.status != "owner":
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    # Then the groups and the church (the order of locks in services/locks.py).
    groups = list(
        db.scalars(
            select(HomeGroup)
            .where(HomeGroup.church_id == church.id, HomeGroup.closed_at.is_(None))
            .order_by(HomeGroup.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    locked_church = db.get(Church, church.id, with_for_update=True, populate_existing=True)
    if locked_church is None or locked_church.closed_at is not None:
        raise ApiError(409, "state_changed", "The church changed meanwhile. Reload.")
    # Someone who joined between the first read and the locks is a member too.
    members = [
        p
        for p in people.values()
        if p.id != owner.id
        and p.church_id == church.id
        and p.closed_at is None
        and p.status != "revoked"  # revoked since the first read: they stay revoked and open
    ]
    late = list(
        db.scalars(
            select(Person).where(
                Person.church_id == church.id,
                Person.closed_at.is_(None),
                Person.status != "revoked",
                Person.id.not_in([p.id for p in members]),
            )
        )
    )
    if late:
        raise ApiError(409, "state_changed", "The church changed meanwhile. Reload.")
    now = datetime.now(UTC)
    group_ids = [g.id for g in groups]
    if group_ids:
        db.execute(
            update(GroupInvitation)
            .where(
                GroupInvitation.home_group_id.in_(group_ids), GroupInvitation.revoked_at.is_(None)
            )
            .values(revoked_at=now)
        )
        db.execute(
            update(MoveRequest)
            .where(
                MoveRequest.completed_at.is_(None),
                MoveRequest.cancelled_at.is_(None),
                (MoveRequest.from_group_id.in_(group_ids))
                | (MoveRequest.to_group_id.in_(group_ids)),
            )
            .values(cancelled_at=now)
        )
    db.execute(
        update(GroupRequest)
        .where(GroupRequest.church_id == church.id, GroupRequest.state == "open")
        .values(state="declined", decided_by_id=owner.id, decided_at=now)
    )
    for group in groups:
        group.closed_at = now
    account_closing.clear_accounts(db, members, now)
    locked_church.closed_at = now
    return locked_church, len(groups), len(members)
