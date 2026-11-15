"""Reading churches, home groups and people for the screens of the church trust model."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.church import Church, HomeGroup, Person
from app.models.trust import Vouch
from app.schemas.church import (
    ChurchSummary,
    HomeGroupSummary,
    IdName,
    NameRef,
    PersonMeResponse,
)
from app.schemas.church_invitations import ChurchSummaryOwner
from app.services.permissions import live_vouches

# The number of churches and groups is small and set by the operators; this is a safety net so the
# public lists can never grow without bound.
MAX_LISTED = 500


def open_churches(db: Session) -> list[ChurchSummary]:
    rows = db.execute(
        select(Church.id, Church.name)
        .where(Church.closed_at.is_(None))
        .order_by(func.lower(Church.name))
        .limit(MAX_LISTED)
    ).all()
    return [ChurchSummary(id=row.id, name=row.name) for row in rows]


def open_home_groups(db: Session, church_id: uuid.UUID) -> list[HomeGroupSummary] | None:
    """The open groups of an open church with their leaders' names, or None if there is no such
    church (unknown or closed)."""
    church = db.get(Church, church_id)
    if church is None or church.closed_at is not None:
        return None
    rows = db.execute(
        select(HomeGroup.id, HomeGroup.name, Person.full_name)
        .join(Person, Person.id == HomeGroup.leader_id)
        .where(HomeGroup.church_id == church_id, HomeGroup.closed_at.is_(None))
        .order_by(func.lower(HomeGroup.name))
        .limit(MAX_LISTED)
    ).all()
    return [
        HomeGroupSummary(id=row.id, name=row.name, leader_name=row.full_name or "") for row in rows
    ]


def person_view(db: Session, person: Person) -> PersonMeResponse:
    church = db.get(Church, person.church_id)
    group = db.get(HomeGroup, person.home_group_id) if person.home_group_id else None
    leader = db.get(Person, group.leader_id) if group else None
    set_by = db.get(Person, person.status_set_by_id) if person.status_set_by_id else None
    vouches = db.execute(
        select(Vouch.voucher_id, Vouch.withdrawn_at).where(Vouch.applicant_id == person.id)
    ).all()
    vouchers = {
        p.id: p
        for p in db.scalars(select(Person).where(Person.id.in_([v.voucher_id for v in vouches])))
    }
    if church is None:  # cannot happen: the foreign key guarantees a church
        raise LookupError("a person without a church")
    return PersonMeResponse(
        id=person.id,
        full_name=person.full_name or "",
        email=person.email or "",
        mobile_number=person.mobile_number or "",
        status=person.status,
        requested_status=person.requested_status,
        church=IdName(id=church.id, name=church.name),
        home_group=IdName(id=group.id, name=group.name) if group else None,
        leader=NameRef(name=leader.full_name or "") if leader else None,
        status_set_by=NameRef(name=set_by.full_name or "") if set_by else None,
        flagged_for_recheck=person.flagged_for_recheck,
        vouch_count=len(live_vouches([(v.voucher_id, v.withdrawn_at) for v in vouches], vouchers)),
    )


def owner_churches(db: Session, *, limit: int, offset: int) -> tuple[list[ChurchSummaryOwner], int]:
    """Every church, open first and then by name, with counts, for the OWNER."""
    total = db.scalar(select(func.count()).select_from(Church)) or 0
    churches = list(
        db.scalars(
            select(Church)
            .order_by(Church.closed_at.is_not(None), func.lower(Church.name), Church.id)
            .limit(limit)
            .offset(offset)
        )
    )
    if not churches:
        return [], total
    ids = [c.id for c in churches]
    groups: dict[uuid.UUID, int] = {}
    for church_id, count in db.execute(
        select(HomeGroup.church_id, func.count())
        .where(HomeGroup.church_id.in_(ids), HomeGroup.closed_at.is_(None))
        .group_by(HomeGroup.church_id)
    ):
        groups[church_id] = count
    people = db.execute(
        select(Person.church_id, Person.status, func.count())
        .where(Person.church_id.in_(ids), Person.closed_at.is_(None))
        .group_by(Person.church_id, Person.status)
    ).all()
    members: dict[uuid.UUID, int] = {}
    revoked: dict[uuid.UUID, int] = {}
    for church_id, status, count in people:
        target = revoked if status == "revoked" else members
        target[church_id] = target.get(church_id, 0) + count
    admins = {
        p.id: p.full_name or ""
        for p in db.scalars(select(Person).where(Person.id.in_([c.admin_id for c in churches])))
    }
    return [
        ChurchSummaryOwner(
            id=c.id,
            name=c.name,
            admin_name=admins.get(c.admin_id, ""),
            admin_id=c.admin_id if c.closed_at is None else None,
            open=c.closed_at is None,
            groups=groups.get(c.id, 0),
            members=members.get(c.id, 0),
            revoked=revoked.get(c.id, 0),
            closed_at=c.closed_at,
        )
        for c in churches
    ], total
