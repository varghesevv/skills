"""Signing up, changing the choice while pending, and the home group invitation link.

Rules (docs/verification.md, "Joining"): sign-up is complete only when a home group is chosen, so
nobody is PENDING without one; email and mobile number are unique among open accounts, revoked
ones included; the chosen leader is notified; link tokens are long, random and stored hashed, and
every failure of a link looks the same.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_password, hash_token, new_opaque_token
from app.models.church import Church, HomeGroup, Person
from app.models.trust import GroupInvitation, Notification, StatusChange
from app.schemas.signup import GroupInvitationInfo

NEW_APPLICANT = "applicant_new"  # notification kind: a person applied to your home group


def _account_exists() -> ApiError:
    # One answer for an email and for a mobile number, so it does not say which one matched.
    return ApiError(409, "account_exists", "An account with these details already exists")


def _invalid_choice() -> ApiError:
    return ApiError(422, "invalid_choice", "That home group is not available")


def open_group(db: Session, group_id: uuid.UUID) -> tuple[HomeGroup, Church] | None:
    """The home group and its church, if both are open."""
    group = db.get(HomeGroup, group_id)
    if group is None or group.closed_at is not None:
        return None
    church = db.get(Church, group.church_id)
    if church is None or church.closed_at is not None:
        return None
    return group, church


def _notify_leader(db: Session, group: HomeGroup, applicant_id: uuid.UUID) -> None:
    db.add(Notification(person_id=group.leader_id, kind=NEW_APPLICANT, subject_id=applicant_id))


def sign_up(
    db: Session,
    settings: Settings,
    *,
    full_name: str,
    email: str,
    mobile_number: str,
    password: str,
    requested_status: str,
    home_group_id: uuid.UUID | None,
    invitation_token: str | None,
) -> Person:
    # Hash first: a taken address and a free one then cost the same time.
    password_hash = hash_password(password)
    if invitation_token is not None:
        resolved = resolve_group_invitation(db, invitation_token)
        if resolved is None:
            raise _invalid_choice()
        group, church = resolved
    else:
        found = open_group(db, home_group_id) if home_group_id is not None else None
        if found is None:  # the request model guarantees one of the two ways in
            raise _invalid_choice()
        group, church = found
    taken = db.scalar(
        select(Person.id).where(
            Person.closed_at.is_(None),
            or_(Person.email == email.lower(), Person.mobile_number == mobile_number),
        )
    )
    if taken is not None:
        raise _account_exists()
    person = Person(
        id=uuid.uuid4(),
        status="pending",
        church_id=church.id,
        home_group_id=group.id,
        full_name=full_name,
        email=email.lower(),
        mobile_number=mobile_number,
        password_hash=password_hash,
        requested_status=requested_status,
    )
    db.add(person)
    db.flush()
    db.add(
        StatusChange(
            person_id=person.id,
            from_status=None,
            to_status="pending",
            changed_by_id=None,
            kind="signup",
        )
    )
    _notify_leader(db, group, person.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # two sign-ups with the same details at once: the database let one win
        raise _account_exists() from None
    return person


def change_application(
    db: Session,
    person: Person,
    *,
    home_group_id: uuid.UUID | None,
    requested_status: str | None,
) -> None:
    """While PENDING: choose another group (even in another church) or another status to apply
    for. Vouches already received stay; a newly chosen leader is notified."""
    if person.status != "pending":
        raise ApiError(409, "not_pending", "Only a pending application can be changed")
    if requested_status is not None:
        person.requested_status = requested_status
    if home_group_id is not None and home_group_id != person.home_group_id:
        found = open_group(db, home_group_id)
        if found is None:
            raise _invalid_choice()
        group, church = found
        person.church_id = church.id
        person.home_group_id = group.id
        _notify_leader(db, group, person.id)
    db.commit()


# ---- group invitation links ---------------------------------------------------------------


def create_group_invitation(
    db: Session, settings: Settings, leader: Person
) -> tuple[GroupInvitation, str]:
    """A new link into the leader's own home group. The token is returned once."""
    if leader.home_group_id is None:
        raise ApiError(409, "no_home_group", "You do not lead a home group")
    token = new_opaque_token()
    invitation = GroupInvitation(
        home_group_id=leader.home_group_id,
        created_by_id=leader.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.invitation_link_days),
    )
    db.add(invitation)
    db.commit()
    return invitation, token


def active_invitations(db: Session, leader: Person) -> list[GroupInvitation]:
    now = datetime.now(UTC)
    return list(
        db.scalars(
            select(GroupInvitation)
            .where(
                GroupInvitation.home_group_id == leader.home_group_id,
                GroupInvitation.revoked_at.is_(None),
                GroupInvitation.expires_at > now,
            )
            .order_by(GroupInvitation.created_at.desc())
        )
    )


def revoke_invitation(db: Session, leader: Person, invitation_id: uuid.UUID) -> None:
    invitation = db.get(GroupInvitation, invitation_id)
    if invitation is None or invitation.home_group_id != leader.home_group_id:
        raise ApiError(404, "not_found", "There is no such link")
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
        db.commit()


def resolve_group_invitation(db: Session, token: str) -> tuple[HomeGroup, Church] | None:
    """The group and church a link leads to, or None for every kind of failure alike: no such
    link, expired, revoked, or the group or church closed since."""
    invitation = db.scalar(
        select(GroupInvitation).where(GroupInvitation.token_hash == hash_token(token))
    )
    if (
        invitation is None
        or invitation.revoked_at is not None
        or invitation.expires_at <= datetime.now(UTC)
    ):
        return None
    return open_group(db, invitation.home_group_id)


def invitation_info(db: Session, token: str) -> GroupInvitationInfo | None:
    resolved = resolve_group_invitation(db, token)
    if resolved is None:
        return None
    group, church = resolved
    leader = db.get(Person, group.leader_id)
    return GroupInvitationInfo(
        church_name=church.name,
        home_group_name=group.name,
        leader_name=(leader.full_name if leader else "") or "",
    )
