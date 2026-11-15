"""What the verifier screens read: applicants, members, the revoked, the flagged, one person.

Every list is limited to the caller's scope (see `permissions.in_scope`), excludes closed accounts
and carries no phone number. The one exception is `person_detail`, which logs each view.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Church, HomeGroup, Person
from app.models.enums import STATUS_RANK, STATUSES
from app.models.trust import ContactView, StatusChange, Vouch
from app.schemas.church import IdName, NameRef
from app.schemas.verifier import (
    ApplicantList,
    ApplicantRow,
    ChainLink,
    FlaggedList,
    FlaggedRow,
    HistoryEntry,
    MemberList,
    MemberRow,
    PersonDetail,
    RevokedList,
    RevokedRow,
    Voucher,
)
from app.services.permissions import can_admit, in_scope

ADMITTED_STATUSES = tuple(s for s in STATUSES if STATUS_RANK[s] >= STATUS_RANK["searcher"])
MAX_HISTORY = 100
MAX_CHAIN = 20  # the chain ends at the OWNER; the cap only guards against bad data


def scope_clause(actor: Person) -> ColumnElement[bool]:
    """The SQL twin of `permissions.in_scope` for a verifier actor."""
    if actor.status == "owner":
        return true()
    if actor.status == "admin":
        return Person.church_id == actor.church_id
    if actor.home_group_id is None:
        return false()
    # A revoked person is in the scope of the group they were removed from. Written as an OR so
    # the indexes on both columns can be used.
    return or_(
        Person.home_group_id == actor.home_group_id,
        and_(Person.home_group_id.is_(None), Person.last_home_group_id == actor.home_group_id),
    )


def _in_scope_people(actor: Person) -> Select[tuple[Person]]:
    return select(Person).where(Person.closed_at.is_(None), scope_clause(actor))


def _page(
    db: Session, query: Select[tuple[Person]], order: Sequence[Any], limit: int, offset: int
) -> tuple[list[Person], int]:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = list(db.scalars(query.order_by(*order, Person.id).limit(limit).offset(offset)))
    return rows, total


def _names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {
        p.id: p.full_name or "" for p in db.scalars(select(Person).where(Person.id.in_(wanted)))
    }


def _groups(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, IdName]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {
        g.id: IdName(id=g.id, name=g.name)
        for g in db.scalars(select(HomeGroup).where(HomeGroup.id.in_(wanted)))
    }


def _name_ref(names: dict[uuid.UUID, str], person_id: uuid.UUID | None) -> NameRef | None:
    return NameRef(name=names.get(person_id, "")) if person_id is not None else None


def _vouch_rows(db: Session, applicant_ids: list[uuid.UUID]) -> list[tuple[Vouch, Person, str]]:
    """The vouches the applicants received, newest first, with each voucher and their church."""
    if not applicant_ids:
        return []
    rows = db.execute(
        select(Vouch, Person, Church.name)
        .join(Person, Person.id == Vouch.voucher_id)
        .join(Church, Church.id == Person.church_id)
        .where(Vouch.applicant_id.in_(applicant_ids))
        .order_by(Vouch.created_at.desc(), Vouch.id)
    ).all()
    return [(vouch, voucher, church_name) for vouch, voucher, church_name in rows]


def _counts(vouch: Vouch, voucher: Person) -> bool:
    return (
        vouch.withdrawn_at is None
        and voucher.closed_at is None
        and voucher.status in ADMITTED_STATUSES
    )


def _vouchers(
    applicant_ids: list[uuid.UUID], rows: list[tuple[Vouch, Person, str]]
) -> dict[uuid.UUID, list[Voucher]]:
    """The vouches each applicant received, newest first, with whether each still counts."""
    result: dict[uuid.UUID, list[Voucher]] = {i: [] for i in applicant_ids}
    for vouch, voucher, church_name in rows:
        result[vouch.applicant_id].append(
            Voucher(
                name=voucher.full_name or "",
                church_name=church_name,
                live=_counts(vouch, voucher),
            )
        )
    return result


def _live_voucher_ids(
    vouch_rows: list[tuple[Vouch, Person, str]],
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """The ids of the people whose vouches count, for each applicant (grouped once)."""
    live: dict[uuid.UUID, list[uuid.UUID]] = {}
    for vouch, giver, _ in vouch_rows:
        if _counts(vouch, giver):
            live.setdefault(vouch.applicant_id, []).append(giver.id)
    return live


def _can_admit_as_provider(
    actor: Person, person: Person, live: dict[uuid.UUID, list[uuid.UUID]]
) -> bool:
    """Whether `admit` would take this person as a provider now: an applicant, or a searcher who
    asked to become one, with a live vouch from someone besides the caller."""
    waiting = person.status == "pending" or (
        person.status == "searcher" and person.requested_status == "provider"
    )
    return waiting and can_admit(actor, person, "provider", live.get(person.id, []))


def applicants(db: Session, actor: Person, limit: int, offset: int) -> ApplicantList:
    """PENDING applicants in scope, the most vouched first."""
    voucher = select(Person.id).where(
        Person.closed_at.is_(None), Person.status.in_(ADMITTED_STATUSES)
    )
    live_count = (
        select(func.count())
        .select_from(Vouch)
        .where(
            Vouch.applicant_id == Person.id,
            Vouch.withdrawn_at.is_(None),
            Vouch.voucher_id.in_(voucher),
        )
        .correlate(Person)
        .scalar_subquery()
    )
    # Pending applicants, and searchers who asked to become providers.
    query = _in_scope_people(actor).where(
        or_(
            Person.status == "pending",
            and_(Person.status == "searcher", Person.requested_status == "provider"),
        )
    )
    rows, total = _page(db, query, [live_count.desc(), Person.created_at], limit, offset)
    ids = [p.id for p in rows]
    vouch_rows = _vouch_rows(db, ids)  # read once: the list and the flag come from the same rows
    vouchers = _vouchers(ids, vouch_rows)
    live_ids = _live_voucher_ids(vouch_rows)
    groups = _groups(db, {p.home_group_id for p in rows})
    return ApplicantList(
        total=total,
        items=[
            ApplicantRow(
                id=p.id,
                full_name=p.full_name or "",
                status=p.status,
                requested_status=p.requested_status,
                home_group=groups[p.home_group_id],  # type: ignore[index]  # has a group
                applied_at=p.created_at,
                vouch_count=sum(v.live for v in vouchers[p.id]),
                vouchers=vouchers[p.id],
                can_admit_as_provider=_can_admit_as_provider(actor, p, live_ids),
            )
            for p in rows
        ],
    )


def members(
    db: Session,
    actor: Person,
    limit: int,
    offset: int,
    *,
    status: str | None,
    home_group_id: uuid.UUID | None,
    church_id: uuid.UUID | None = None,
) -> MemberList:
    query = _in_scope_people(actor).where(Person.status.in_(ADMITTED_STATUSES))
    if status is not None:
        query = query.where(Person.status == status)
    if home_group_id is not None:
        query = query.where(Person.home_group_id == home_group_id)
    if church_id is not None:
        query = query.where(Person.church_id == church_id)
    rows, total = _page(db, query, [func.lower(Person.full_name)], limit, offset)
    names = _names(db, {p.status_set_by_id for p in rows})
    groups = _groups(db, {p.home_group_id for p in rows})
    return MemberList(
        total=total,
        items=[
            MemberRow(
                id=p.id,
                full_name=p.full_name or "",
                status=p.status,
                home_group=groups.get(p.home_group_id) if p.home_group_id else None,
                status_set_by=_name_ref(names, p.status_set_by_id),
                flagged_for_recheck=p.flagged_for_recheck,
            )
            for p in rows
        ],
    )


def revoked(db: Session, actor: Person, limit: int, offset: int) -> RevokedList:
    query = _in_scope_people(actor).where(Person.status == "revoked")
    rows, total = _page(db, query, [func.lower(Person.full_name)], limit, offset)
    # The latest revocation of each person says who revoked them and when.
    changes = db.scalars(
        select(StatusChange)
        .where(
            StatusChange.person_id.in_([p.id for p in rows]), StatusChange.to_status == "revoked"
        )
        .order_by(StatusChange.at.desc(), StatusChange.id)
    )
    latest: dict[uuid.UUID, StatusChange] = {}
    for change in changes:
        latest.setdefault(change.person_id, change)
    names = _names(db, {c.changed_by_id for c in latest.values()})
    groups = _groups(db, {p.last_home_group_id for p in rows})
    return RevokedList(
        total=total,
        items=[
            RevokedRow(
                id=p.id,
                full_name=p.full_name or "",
                removed_from=groups.get(p.last_home_group_id) if p.last_home_group_id else None,
                revoked_by=_name_ref(names, latest[p.id].changed_by_id) if p.id in latest else None,
                revoked_at=latest[p.id].at if p.id in latest else None,
            )
            for p in rows
        ],
    )


def flagged(db: Session, actor: Person, limit: int, offset: int) -> FlaggedList:
    query = _in_scope_people(actor).where(Person.flagged_for_recheck.is_(True))
    rows, total = _page(db, query, [func.lower(Person.full_name)], limit, offset)
    names = _names(db, {p.status_set_by_id for p in rows})
    groups = _groups(db, {p.home_group_id or p.last_home_group_id for p in rows})
    return FlaggedList(
        total=total,
        items=[
            FlaggedRow(
                id=p.id,
                full_name=p.full_name or "",
                status=p.status,
                home_group=groups.get(p.home_group_id or p.last_home_group_id),  # type: ignore[arg-type]
                status_set_by=_name_ref(names, p.status_set_by_id),
            )
            for p in rows
        ],
    )


def person_detail(db: Session, actor: Person, person_id: uuid.UUID) -> PersonDetail:
    """One person in scope, with the number. Each call is logged, without the number."""
    person = db.get(Person, person_id)
    if person is None or person.closed_at is not None or not in_scope(actor, person):
        raise ApiError(404, "not_found", "There is no such person")
    db.add(ContactView(viewer_id=actor.id, person_id=person.id, screen="person"))
    history = list(
        db.scalars(
            select(StatusChange)
            .where(StatusChange.person_id == person.id)
            .order_by(StatusChange.at.desc(), StatusChange.id)
            .limit(MAX_HISTORY)
        )
    )
    chain: list[Person] = []
    seen = {person.id}
    setter_id = person.status_set_by_id
    while setter_id is not None and setter_id not in seen and len(chain) < MAX_CHAIN:
        setter = db.get(Person, setter_id)
        if setter is None:
            break
        chain.append(setter)
        seen.add(setter.id)
        setter_id = setter.status_set_by_id
    names = _names(db, {c.changed_by_id for c in history} | {person.status_set_by_id})
    group_id = person.home_group_id or person.last_home_group_id
    group = db.get(HomeGroup, group_id) if group_id else None
    church = db.get(Church, person.church_id)
    vouch_rows = _vouch_rows(db, [person.id])
    detail = PersonDetail(
        id=person.id,
        full_name=person.full_name or "",
        mobile_number=person.mobile_number or "",
        status=person.status,
        requested_status=person.requested_status,
        church=IdName(id=person.church_id, name=church.name if church else ""),
        home_group=IdName(id=group.id, name=group.name) if group else None,
        status_set_by=_name_ref(names, person.status_set_by_id),
        flagged_for_recheck=person.flagged_for_recheck,
        applied_at=person.created_at,
        history=[
            HistoryEntry(
                kind=c.kind,
                from_status=c.from_status,
                to_status=c.to_status,
                changed_by=_name_ref(names, c.changed_by_id),
                at=c.at,
            )
            for c in history
        ],
        chain_of_trust=[
            ChainLink(id=c.id, full_name=c.full_name or "", status=c.status) for c in chain
        ],
        vouches=_vouchers([person.id], vouch_rows)[person.id],
        can_admit_as_provider=_can_admit_as_provider(actor, person, _live_voucher_ids(vouch_rows)),
    )
    db.commit()  # the log row and nothing else
    return detail
