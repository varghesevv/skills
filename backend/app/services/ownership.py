"""Changing the OWNER (docs/verification.md, "Owner succession").

There is always exactly one OWNER, who is also the ADMIN of their own church and usually leads a
home group. A change of OWNER moves several roles in one transaction:

- the chosen ADMIN of another church becomes the OWNER, and stays the ADMIN of their own church
  (every OWNER is), keeping any group they lead;
- the outgoing OWNER's own church gets a new ADMIN and their group a new leader, named by the
  outgoing OWNER; with nobody else in the church (or the group) they keep that role instead;
- the outgoing OWNER becomes a PROVIDER or a SEARCHER in their home group (an ADMIN, or a VERIFIER,
  if they keep a role), set by the new OWNER.

A planned handover is made by the OWNER and accepted by the chosen ADMIN (`handover.py`). When the
OWNER cannot hand over, or has breached trust, the platform operators do the same by a command on
the server (`operators.py`); a breach of trust revokes the outgoing OWNER, which flags everyone
whose status they set, and the new OWNER clears those flags.

This module makes the change; the caller locks the people first, checks who may ask, and commits.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.trust import Notification, StatusChange
from app.services import succession
from app.services.revocation import flag_people_set_by

ADMIN_APPOINTED = succession.ADMIN_APPOINTED
LEADER_APPOINTED = succession.LEADER_APPOINTED
OWNER_HANDED_OVER = "owner_handed_over"  # notification kind: the OWNER role passed to someone
OWNER_APPOINTED = "owner_appointed"  # notification kind: you are now the OWNER


def _row(
    person: Person, previous: str, to: str, by: Person | None, kind: str, at: datetime
) -> StatusChange:
    return StatusChange(
        person_id=person.id,
        from_status=previous,
        to_status=to,
        changed_by_id=by.id if by is not None else None,
        kind=kind,
        at=at,
    )


def _open_members(db: Session, church_id: uuid.UUID, excluding: uuid.UUID) -> list[Person]:
    return list(
        db.scalars(
            select(Person).where(
                Person.church_id == church_id,
                Person.id != excluding,
                Person.closed_at.is_(None),
                Person.status != "revoked",
            )
        )
    )


def check_admin_successor(
    db: Session, church: Church, old: Person, successor_id: uuid.UUID | None
) -> Person | None:
    """The member of the outgoing OWNER's church who becomes its ADMIN, if one is named. Without
    one, the outgoing OWNER keeps the role, which only works when nobody else is in the church."""
    if successor_id is None:
        if _open_members(db, church.id, old.id):
            raise ApiError(
                409,
                "successor_required",
                "Name a new ADMIN for the church: it has other members",
            )
        return None
    return succession.pick_church_successor(db, church, old, successor_id)


def check_leader_successor(
    db: Session, group: HomeGroup | None, old: Person, successor_id: uuid.UUID | None
) -> Person | None:
    """The member of the outgoing OWNER's group who leads it from now on, if they lead one."""
    if group is None or group.closed_at is not None or group.leader_id != old.id:
        if successor_id is not None:
            raise ApiError(422, "invalid_choice", "The OWNER leads no group to hand on")
        return None
    if successor_id is None:
        if succession.other_members(db, group, old.id):
            raise ApiError(
                409, "successor_required", "Name a new leader for the group: it has other members"
            )
        return None
    return succession.pick_successor(db, group, old, successor_id)


def transfer(
    db: Session,
    *,
    old: Person,
    new: Person,
    admin_successor_id: uuid.UUID | None,
    leader_successor_id: uuid.UUID | None,
    former_status: str,
    kind: str,
    revoke_old: bool = False,
) -> None:
    """Make `new` (the ADMIN of another church) the OWNER and move the other roles. `kind` is
    `handover` (the people involved are the actors) or `operator` (no person is). The people are
    locked and checked by the caller; this reads the groups and churches under their own locks."""
    handover = kind == "handover"
    group = (
        db.get(HomeGroup, old.home_group_id, with_for_update=True) if old.home_group_id else None
    )
    ids = sorted({old.church_id, new.church_id}, key=str)
    churches = {i: db.get(Church, i, with_for_update=True, populate_existing=True) for i in ids}
    church_old, church_new = churches[old.church_id], churches[new.church_id]
    if (
        old.status != "owner"
        or new.status != "admin"
        or new.closed_at is not None
        or old.church_id == new.church_id
        or church_old is None
        or church_new is None
        or church_old.closed_at is not None
        or church_new.closed_at is not None
        or church_new.admin_id != new.id
        or church_old.admin_id != old.id
    ):
        raise ApiError(409, "state_changed", "The people or churches changed meanwhile. Reload.")
    admin_successor = check_admin_successor(db, church_old, old, admin_successor_id)
    leads = group is not None and group.closed_at is None and group.leader_id == old.id
    leader_successor = check_leader_successor(db, group, old, leader_successor_id)
    keeps_church = admin_successor is None
    keeps_group = leads and leader_successor is None
    if revoke_old and keeps_church:
        raise ApiError(
            409, "successor_required", "A revoked OWNER cannot keep their church: name a new ADMIN"
        )
    now = datetime.now(UTC)
    # The new OWNER first: from now on the people they appoint are set by them.
    new_by = old if handover else None
    db.add(_row(new, "admin", "owner", new_by, kind, now))
    new.status = "owner"
    new.status_set_by_id = None  # the root of the chain of trust, like the first OWNER
    appointer = new if handover else None
    if admin_successor is not None:
        db.add(
            _row(
                admin_successor,
                admin_successor.status,
                "admin",
                appointer,
                "appoint" if handover else kind,
                now,
            )
        )
        admin_successor.status = "admin"
        admin_successor.status_set_by_id = new.id if handover else None
        church_old.admin_id = admin_successor.id
        if handover:
            db.add(
                Notification(person_id=admin_successor.id, kind=ADMIN_APPOINTED, subject_id=new.id)
            )
    if leader_successor is not None and group is not None:
        if leader_successor.status in ("pending", "searcher", "provider"):
            db.add(
                _row(
                    leader_successor,
                    leader_successor.status,
                    "verifier",
                    appointer,
                    "appoint" if handover else kind,
                    now,
                )
            )
            leader_successor.status = "verifier"
            leader_successor.status_set_by_id = new.id if handover else None
        group.leader_id = leader_successor.id
        if handover:
            db.add(
                Notification(
                    person_id=leader_successor.id, kind=LEADER_APPOINTED, subject_id=new.id
                )
            )
    if leads and leader_successor is not None and group is not None:
        succession.revoke_invitations(db, old, group)
    if revoke_old:
        if leads and group is not None and leader_successor is None:
            group.closed_at = now  # they were alone in it
            succession.revoke_invitations(db, old, group)
        old_group_id = old.home_group_id
        db.add(_row(old, "owner", "revoked", None, kind, now))
        flag_people_set_by(db, old)
        old.last_home_group_id = old_group_id
        old.home_group_id = None
        old.status = "revoked"
        old.requested_status = None
        old.flagged_for_recheck = False
        old.status_set_by_id = None
        return
    if keeps_church:
        new_status = "admin"
    elif keeps_group:
        new_status = "verifier"
    else:
        new_status = former_status
    db.add(_row(old, "owner", new_status, new if handover else None, kind, now))
    old.status = new_status
    old.status_set_by_id = new.id if handover else None
    if handover:
        db.add(Notification(person_id=old.id, kind=OWNER_HANDED_OVER, subject_id=new.id))
        db.add(Notification(person_id=new.id, kind=OWNER_APPOINTED, subject_id=old.id))
