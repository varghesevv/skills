import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_principal, require_roles
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.availability import FreelancerUnavailability
from app.models.labels import FreelancerLabel, Label
from app.models.ratings import UserRating
from app.models.users import Freelancer, Organisation
from app.models.vouching import OrgFreelancer
from app.schemas.common import Page, Pagination, pagination
from app.schemas.profiles import (
    FreelancerLabelOut,
    FreelancerMe,
    FreelancerPublic,
    FreelancerUpdate,
    GivenRating,
    LabelsUpdate,
    PublicRating,
    RevealedMobile,
    RevealRequest,
    UnavailabilityIn,
    UnavailabilityOut,
    VouchingOrg,
    VouchOut,
)
from app.services.profiles import (
    current_account,
    freelancer_labels,
    rating_summary,
    to_float,
    utc_now,
)
from app.services.reveals import reveal_mobile_number

router = APIRouter(prefix="/freelancers", tags=["freelancers"])

FreelancerOnly = Annotated[Principal, Depends(require_roles("freelancer"))]
Viewer = Annotated[Principal, Depends(require_roles("workhost", "organisation", "admin"))]
Authenticated = Annotated[Principal, Depends(get_principal)]


def _me(db: Session, principal: Principal) -> Freelancer:
    return current_account(db, Freelancer, principal)


def _me_response(db: Session, me: Freelancer) -> FreelancerMe:
    return FreelancerMe(
        id=me.id,
        full_name=me.full_name,
        email=me.user_email,
        mobile_number=me.mobile_number,
        whatsapp_availability=me.whatsapp_availability,
        nationality=me.nationality,
        primary_language=me.primary_language,
        rate_per_hour=to_float(me.rate_per_hour),
        rate_currency=me.rate_currency,
        is_rate_negotiable=me.is_rate_negotiable,
        labels=freelancer_labels(db, me.id),
        created_at=me.created_at,
    )


# ---- own profile --------------------------------------------------------------------------


@router.get("/me")
def get_me(principal: FreelancerOnly, db: Session = Depends(get_session)) -> FreelancerMe:
    return _me_response(db, _me(db, principal))


@router.put("/me")
def update_me(
    body: FreelancerUpdate, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> FreelancerMe:
    me = _me(db, principal)
    if body.full_name is not None:
        me.full_name = body.full_name
    me.mobile_number = body.mobile_number
    me.whatsapp_availability = body.whatsapp_availability
    me.nationality = body.nationality
    me.primary_language = body.primary_language
    me.rate_per_hour = body.rate_per_hour
    me.rate_currency = body.rate_currency
    me.is_rate_negotiable = body.is_rate_negotiable
    db.commit()
    return _me_response(db, me)


@router.put("/me/labels")
def replace_labels(
    body: LabelsUpdate, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> list[FreelancerLabelOut]:
    """Replace the freelancer's whole label set. Skill levels attach to a specific skill."""
    me = _me(db, principal)
    chosen = [selection.label_id for selection in body.labels]
    if len(set(chosen)) != len(chosen):
        raise ApiError(422, "duplicate_label", "A label was selected more than once")
    wanted = set(chosen) | {s.level_label_id for s in body.labels if s.level_label_id}
    active_labels = db.scalars(select(Label).where(Label.id.in_(wanted), Label.is_active.is_(True)))
    found = {label.id: label for label in active_labels}
    if wanted - found.keys():
        raise ApiError(422, "unknown_label", "A label does not exist or is not active")
    for selection in body.labels:
        label = found[selection.label_id]
        if label.label_type == "skill_level":
            raise ApiError(
                422, "level_not_selectable", "A skill level can only be attached to a skill"
            )
        if selection.level_label_id is not None and (
            label.label_type != "skill"
            or found[selection.level_label_id].label_type != "skill_level"
        ):
            raise ApiError(
                422, "invalid_level", "Only skills take a level, and it must be a skill level"
            )
    db.execute(delete(FreelancerLabel).where(FreelancerLabel.freelancer_id == me.id))
    db.add_all(
        FreelancerLabel(freelancer_id=me.id, label_id=s.label_id, level_label_id=s.level_label_id)
        for s in body.labels
    )
    db.commit()
    return freelancer_labels(db, me.id)


# ---- unavailability -----------------------------------------------------------------------


def _unavailability_out(row: FreelancerUnavailability) -> UnavailabilityOut:
    return UnavailabilityOut(
        id=row.id, unavailable_from=row.unavailable_from, unavailable_to=row.unavailable_to
    )


def _commit_unavailability(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(
            409, "unavailability_overlaps", "This period overlaps one you already have"
        ) from None


def _own_period(db: Session, me: Freelancer, period_id: uuid.UUID) -> FreelancerUnavailability:
    row = db.get(FreelancerUnavailability, period_id)
    if row is None or row.freelancer_id != me.id:
        raise ApiError(404, "not_found", "Unavailability period not found")
    return row


@router.get("/me/unavailability")
def list_unavailability(
    principal: FreelancerOnly, db: Session = Depends(get_session)
) -> list[UnavailabilityOut]:
    rows = db.scalars(
        select(FreelancerUnavailability)
        .where(FreelancerUnavailability.freelancer_id == principal.user_id)
        .order_by(FreelancerUnavailability.unavailable_from)
    ).all()
    return [_unavailability_out(row) for row in rows]


@router.post("/me/unavailability", status_code=status.HTTP_201_CREATED)
def add_unavailability(
    body: UnavailabilityIn, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> UnavailabilityOut:
    row = FreelancerUnavailability(
        freelancer_id=_me(db, principal).id,
        unavailable_from=body.unavailable_from,
        unavailable_to=body.unavailable_to,
    )
    db.add(row)
    _commit_unavailability(db)
    return _unavailability_out(row)


@router.put("/me/unavailability/{period_id}")
def update_unavailability(
    period_id: uuid.UUID,
    body: UnavailabilityIn,
    principal: FreelancerOnly,
    db: Session = Depends(get_session),
) -> UnavailabilityOut:
    row = _own_period(db, _me(db, principal), period_id)
    row.unavailable_from = body.unavailable_from
    row.unavailable_to = body.unavailable_to
    _commit_unavailability(db)
    return _unavailability_out(row)


@router.delete("/me/unavailability/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unavailability(
    period_id: uuid.UUID, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> Response:
    db.delete(_own_period(db, _me(db, principal), period_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- vouches ------------------------------------------------------------------------------


@router.get("/me/vouches")
def list_vouches(principal: FreelancerOnly, db: Session = Depends(get_session)) -> list[VouchOut]:
    rows = db.execute(
        select(OrgFreelancer, Organisation.org_name)
        .join(Organisation, Organisation.id == OrgFreelancer.org_id)
        .where(OrgFreelancer.freelancer_id == principal.user_id)
        .order_by(OrgFreelancer.created_at)
    ).all()
    return [
        VouchOut(
            org_id=link.org_id,
            org_name=name,
            status=link.status,
            is_active=link.is_active,
            created_at=link.created_at,
        )
        for link, name in rows
    ]


def _decide_vouch(
    db: Session, principal: Principal, org_id: uuid.UUID, *, accept: bool
) -> VouchOut:
    link = db.get(OrgFreelancer, (org_id, principal.user_id))
    org = db.get(Organisation, org_id)
    if link is None or org is None:
        raise ApiError(404, "not_found", "Vouch not found")
    if link.status != "pending":
        raise ApiError(409, "vouch_not_pending", "This vouch has already been decided")
    link.status = "approved" if accept else "revoked"
    link.is_active = accept
    db.commit()
    return VouchOut(
        org_id=org_id,
        org_name=org.org_name,
        status=link.status,
        is_active=link.is_active,
        created_at=link.created_at,
    )


@router.post("/me/vouches/{org_id}/accept")
def accept_vouch(
    org_id: uuid.UUID, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> VouchOut:
    return _decide_vouch(db, principal, org_id, accept=True)


@router.post("/me/vouches/{org_id}/reject")
def reject_vouch(
    org_id: uuid.UUID, principal: FreelancerOnly, db: Session = Depends(get_session)
) -> VouchOut:
    return _decide_vouch(db, principal, org_id, accept=False)


# ---- what others see ----------------------------------------------------------------------


@router.get("/{freelancer_id}")
def public_profile(
    freelancer_id: uuid.UUID, principal: Viewer, db: Session = Depends(get_session)
) -> FreelancerPublic:
    freelancer = db.get(Freelancer, freelancer_id)
    if freelancer is None:
        raise ApiError(404, "not_found", "Freelancer not found")
    average, count = rating_summary(db, freelancer.id)
    orgs = db.execute(
        select(Organisation.id, Organisation.org_name)
        .join(OrgFreelancer, OrgFreelancer.org_id == Organisation.id)
        .where(
            OrgFreelancer.freelancer_id == freelancer.id,
            OrgFreelancer.status == "approved",
            OrgFreelancer.is_active.is_(True),
        )
        .order_by(Organisation.org_name)
    ).all()
    upcoming = db.scalars(
        select(FreelancerUnavailability)
        .where(
            FreelancerUnavailability.freelancer_id == freelancer.id,
            FreelancerUnavailability.unavailable_to > utc_now(),
        )
        .order_by(FreelancerUnavailability.unavailable_from)
    ).all()
    mine = None
    if principal.user_type == "workhost":
        given = db.scalar(
            select(UserRating).where(
                UserRating.work_host_id == principal.user_id,
                UserRating.freelancer_id == freelancer.id,
            )
        )
        if given is not None:
            mine = GivenRating(
                id=given.id,
                freelancer_id=given.freelancer_id,
                freelancer_name=freelancer.full_name,
                rating=given.rating,
                comment=given.comment,
                rated_on=given.rated_on,
                updated_at=given.updated_at,
            )
    return FreelancerPublic(
        id=freelancer.id,
        full_name=freelancer.full_name,
        whatsapp_availability=freelancer.whatsapp_availability,
        nationality=freelancer.nationality,
        primary_language=freelancer.primary_language,
        rate_per_hour=to_float(freelancer.rate_per_hour),
        rate_currency=freelancer.rate_currency,
        is_rate_negotiable=freelancer.is_rate_negotiable,
        labels=freelancer_labels(db, freelancer.id),
        average_rating=average,
        rating_count=count,
        vouched_by=[VouchingOrg(org_id=org_id, org_name=name) for org_id, name in orgs],
        unavailable=[_unavailability_out(row) for row in upcoming],
        my_rating=mine,
    )


HostOnly = Annotated[Principal, Depends(require_roles("workhost"))]


@router.post("/{freelancer_id}/reveal-mobile")
def reveal_mobile(
    freelancer_id: uuid.UUID,
    body: RevealRequest,
    principal: HostOnly,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RevealedMobile:
    """The only place a freelancer's mobile number is returned to anyone else.

    Every call is recorded, and each work host has an hourly and a daily limit.
    """
    number = reveal_mobile_number(
        db, settings, host_id=principal.user_id, freelancer_id=freelancer_id, body=body
    )
    response.headers["Cache-Control"] = "no-store"
    return RevealedMobile(mobile_number=number)


@router.get("/{freelancer_id}/ratings")
def freelancer_ratings(
    freelancer_id: uuid.UUID,
    _: Authenticated,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
) -> Page[PublicRating]:
    if db.get(Freelancer, freelancer_id) is None:
        raise ApiError(404, "not_found", "Freelancer not found")
    where = UserRating.freelancer_id == freelancer_id
    total = db.scalar(select(func.count()).select_from(UserRating).where(where)) or 0
    rows = db.scalars(
        select(UserRating)
        .where(where)
        .order_by(UserRating.rated_on.desc(), UserRating.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[PublicRating](
        items=[PublicRating(rating=r.rating, comment=r.comment, rated_on=r.rated_on) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
