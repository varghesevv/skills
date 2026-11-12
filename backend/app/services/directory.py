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
from app.services.permissions import live_vouches


def open_churches(db: Session) -> list[ChurchSummary]:
    rows = db.execute(
        select(Church.id, Church.name)
        .where(Church.closed_at.is_(None))
        .order_by(func.lower(Church.name))
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
