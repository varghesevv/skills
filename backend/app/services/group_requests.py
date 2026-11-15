"""Starting a home group (docs/verification.md, "Home group leaders", step 2).

Any admitted member can ask to start a home group. The church's ADMIN (or the OWNER) approves, and
in one step the group is created and the member moves into it as its leader (a VERIFIER, unless
they already hold a higher status). An ADMIN or the OWNER starts a group for themselves without
approval. Someone who leads a group now needs a successor for it from its members, named when the
group is started (or the old group closes, if they were its only member).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK
from app.models.trust import GroupRequest, Notification, StatusChange
from app.schemas.church import IdName
from app.schemas.group_requests import GroupRequestOut
from app.services import succession
from app.services.locks import lock_people

GROUP_REQUEST_NEW = "group_request_new"  # notification kind: a member of your church asks
GROUP_REQUEST_APPROVED = "group_request_approved"  # your request was approved
GROUP_REQUEST_DECLINED = "group_request_declined"  # your request was declined


def _leads_a_group(db: Session, person: Person) -> bool:
    group = db.get(HomeGroup, person.home_group_id) if person.home_group_id else None
    return group is not None and group.closed_at is None and group.leader_id == person.id


def _name_taken(db: Session, church_id: uuid.UUID, name: str) -> bool:
    return (
        db.scalar(
            select(HomeGroup.id).where(
                HomeGroup.church_id == church_id,
                HomeGroup.closed_at.is_(None),
                func.lower(HomeGroup.name) == name.lower(),
            )
        )
        is not None
    )


def _open_church(db: Session, church_id: uuid.UUID) -> Church:
    church = db.get(Church, church_id)
    if church is None or church.closed_at is not None:
        raise ApiError(409, "church_closed", "This church is closed")
    return church


def _successor_required() -> ApiError:
    return ApiError(
        409,
        "successor_required",
        "Someone who leads a home group needs a successor for it first",
    )


def _start(db: Session, person: Person, name: str, decided_by: Person | None) -> HomeGroup:
    """Create the group and move the person in as its leader. The caller commits."""
    group = HomeGroup(church_id=person.church_id, name=name, leader_id=person.id)
    db.add(group)
    try:
        db.flush()
    except IntegrityError:
        # The open names of a church are unique: someone took this one a moment ago, after the
        # check above. Nothing is half done.
        db.rollback()
        raise ApiError(
            409, "group_name_taken", "A home group with this name already exists"
        ) from None
    person.home_group_id = group.id
    if STATUS_RANK[person.status] < STATUS_RANK["verifier"]:
        previous = person.status
        person.status = "verifier"
        person.status_set_by_id = decided_by.id if decided_by else None
        if decided_by is not None:
            db.add(
                StatusChange(
                    person_id=person.id,
                    from_status=previous,
                    to_status="verifier",
                    changed_by_id=decided_by.id,
                    kind="appoint",
                    at=datetime.now(UTC),
                )
            )
    return group


def request_group(
    db: Session, person: Person, group_name: str, successor_id: uuid.UUID | None = None
) -> tuple[GroupRequest, HomeGroup | None]:
    """Ask to start a home group. An ADMIN or the OWNER start it at once, and if they lead a group
    now it passes to `successor_id` (or closes, if they are its only member)."""
    own = person.status in ("admin", "owner")
    also = [successor_id] if own and successor_id else []
    if also:
        lock_people(db, [person.id, *also])
    db.refresh(person, with_for_update=True)
    if person.closed_at is not None or person.status in ("revoked", "pending"):
        db.rollback()
        raise ApiError(403, "not_admitted", "This is not available to you yet")
    church = _open_church(db, person.church_id)
    if _name_taken(db, person.church_id, group_name):
        db.rollback()
        raise ApiError(409, "group_name_taken", "A home group with this name already exists")
    if successor_id is not None and not (own and _leads_a_group(db, person)):
        db.rollback()
        raise ApiError(422, "invalid_choice", "There is no group to hand on")
    open_one = db.scalar(
        select(GroupRequest.id).where(
            GroupRequest.requester_id == person.id, GroupRequest.state == "open"
        )
    )
    if open_one is not None:
        db.rollback()
        raise ApiError(409, "request_open", "You already have a request waiting")
    request = GroupRequest(requester_id=person.id, church_id=church.id, group_name=group_name)
    group: HomeGroup | None = None
    if own:
        _leave_old_group(db, person, person, successor_id)
        group = _start(db, person, group_name, None)
        request.state = "approved"
        request.decided_by_id = person.id
        request.decided_at = datetime.now(UTC)
    else:
        db.add(
            Notification(person_id=church.admin_id, kind=GROUP_REQUEST_NEW, subject_id=person.id)
        )
    db.add(request)
    _commit(db)
    return request, group


def _leave_old_group(
    db: Session, person: Person, actor: Person, successor_id: uuid.UUID | None
) -> None:
    """If the person leads a group now, it passes to the successor or closes (the person being
    its only member), in the same transaction as the move to the new one."""
    old = (
        db.get(HomeGroup, person.home_group_id, with_for_update=True)
        if person.home_group_id
        else None
    )
    if old is None or old.closed_at is not None or old.leader_id != person.id:
        if successor_id is not None:
            raise ApiError(422, "invalid_choice", "There is no group to hand on")
        return
    succession.end_leadership(db, old, person, actor, successor_id)


def _views(db: Session, requests: list[GroupRequest]) -> list[GroupRequestOut]:
    people = {
        p.id: p
        for p in db.scalars(select(Person).where(Person.id.in_({r.requester_id for r in requests})))
    }
    churches = {
        c.id: c
        for c in db.scalars(select(Church).where(Church.id.in_({r.church_id for r in requests})))
    }
    # One query for the groups the requesters belong to: to tell who leads one now, and which.
    groups = {
        g.id: g
        for g in db.scalars(
            select(HomeGroup).where(
                HomeGroup.id.in_({p.home_group_id for p in people.values() if p.home_group_id}),
                HomeGroup.closed_at.is_(None),
            )
        )
    }
    views = []
    for r in requests:
        requester = people[r.requester_id]
        group = groups.get(requester.home_group_id) if requester.home_group_id else None
        views.append(
            GroupRequestOut(
                id=r.id,
                group_name=r.group_name,
                church=IdName(id=r.church_id, name=churches[r.church_id].name),
                requester=IdName(id=r.requester_id, name=requester.full_name or ""),
                state=r.state,
                created_at=r.created_at,
                requester_leads_a_group=group is not None and group.leader_id == requester.id,
                requester_group=IdName(id=group.id, name=group.name) if group else None,
            )
        )
    return views


def view(db: Session, request: GroupRequest) -> GroupRequestOut:
    return _views(db, [request])[0]


def listing(
    db: Session, person: Person, *, limit: int, offset: int
) -> tuple[list[GroupRequestOut], int]:
    """An ADMIN's church (the OWNER's every church) sees the open requests; everyone else their
    own, newest first. Returns one page and the total."""
    query = select(GroupRequest)
    if person.status == "owner":
        query = query.where(GroupRequest.state == "open")
    elif person.status == "admin":
        query = query.where(
            GroupRequest.state == "open", GroupRequest.church_id == person.church_id
        )
    else:
        query = query.where(GroupRequest.requester_id == person.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(GroupRequest.created_at.desc(), GroupRequest.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return (_views(db, rows) if rows else []), total


def _decidable(
    db: Session, actor: Person, request_id: uuid.UUID, also: list[uuid.UUID] | None = None
) -> tuple[GroupRequest, Person]:
    """Lock the actor and the requester, and return the open request the actor may decide."""
    found = db.get(GroupRequest, request_id)
    in_scope = found is not None and (actor.status == "owner" or found.church_id == actor.church_id)
    if found is None or not in_scope:
        raise ApiError(404, "not_found", "There is no such request")
    people = lock_people(db, [actor.id, found.requester_id, *(also or [])])
    locked_actor = people.get(actor.id)
    # Read again from the locked row: an ADMIN revoked or changed at this moment decides nothing.
    if (
        locked_actor is None
        or locked_actor.closed_at is not None
        or locked_actor.status not in ("admin", "owner")
        or (locked_actor.status == "admin" and locked_actor.church_id != found.church_id)
    ):
        raise ApiError(403, "forbidden", "You are not allowed to do this")
    request = db.get(GroupRequest, request_id, with_for_update=True, populate_existing=True)
    requester = people.get(found.requester_id)
    if request is None or requester is None:
        raise ApiError(404, "not_found", "There is no such request")
    if request.state != "open":
        raise ApiError(409, "not_open", "This request has been decided")
    return request, requester


def approve(
    db: Session, actor: Person, request_id: uuid.UUID, successor_id: uuid.UUID | None = None
) -> HomeGroup:
    request, requester = _decidable(
        db, actor, request_id, also=[successor_id] if successor_id else []
    )
    _open_church(db, request.church_id)
    if requester.closed_at is not None or requester.status in ("revoked", "pending"):
        raise ApiError(409, "requester_unavailable", "The member is no longer in the church")
    if requester.church_id != request.church_id:
        raise ApiError(409, "requester_unavailable", "The member is no longer in the church")
    if _name_taken(db, request.church_id, request.group_name):
        raise ApiError(409, "group_name_taken", "A home group with this name already exists")
    _leave_old_group(db, requester, actor, successor_id)
    group = _start(db, requester, request.group_name, actor)
    request.state = "approved"
    request.decided_by_id = actor.id
    request.decided_at = datetime.now(UTC)
    db.add(Notification(person_id=requester.id, kind=GROUP_REQUEST_APPROVED, subject_id=actor.id))
    _commit(db)
    return group


def decline(db: Session, actor: Person, request_id: uuid.UUID) -> None:
    request, requester = _decidable(db, actor, request_id)
    request.state = "declined"
    request.decided_by_id = actor.id
    request.decided_at = datetime.now(UTC)
    db.add(Notification(person_id=requester.id, kind=GROUP_REQUEST_DECLINED, subject_id=actor.id))
    _commit(db)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # A name taken at the same moment (the open names are unique), or a state the database
        # refuses; nothing is half done.
        db.rollback()
        raise ApiError(
            409, "state_changed", "Something changed meanwhile. Reload and try again."
        ) from None
