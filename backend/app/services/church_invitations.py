"""Inviting an ADMIN, which creates a church (docs/verification.md, "Setting up Skills").

The OWNER invites the ADMIN of a new church by email, giving the church's name. The church is
created when the invitation is accepted, so it never exists without an ADMIN: in one transaction
the church, its first home group and the ADMIN (who leads the group) are made, and the ADMIN's
status is recorded as set by the OWNER. The invitation link is shown once and stored hashed;
every failure to resolve it is the same `404`.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_password, hash_token, new_opaque_token
from app.models.church import Church, HomeGroup, Person
from app.models.trust import AdminInvitation, Notification, StatusChange
from app.schemas.church_invitations import (
    AdminInvitationAccept,
    AdminInvitationInfo,
    ChurchInvitationSummary,
)

CHURCH_CREATED = "church_created"  # notification kind: an ADMIN accepted and the church exists


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "This invitation is not valid")


def _account_exists() -> ApiError:
    return ApiError(409, "account_exists", "An account with these details already exists")


def _church_name_taken() -> ApiError:
    return ApiError(409, "church_name_taken", "A church with this name already exists")


def _live(invitation: AdminInvitation) -> bool:
    return (
        invitation.accepted_at is None
        and invitation.cancelled_at is None
        and invitation.expires_at > datetime.now(UTC)
    )


def _name_in_use(db: Session, name: str) -> bool:
    """An open church, or an open invitation, already has this name (ignoring case)."""
    lowered = name.lower()
    church = db.scalar(
        select(Church.id).where(Church.closed_at.is_(None), func.lower(Church.name) == lowered)
    )
    invited = db.scalar(
        select(AdminInvitation.id).where(
            AdminInvitation.accepted_at.is_(None),
            AdminInvitation.cancelled_at.is_(None),
            AdminInvitation.expires_at > datetime.now(UTC),
            func.lower(AdminInvitation.church_name) == lowered,
        )
    )
    return church is not None or invited is not None


def invite(
    db: Session, settings: Settings, owner: Person, church_name: str, email: str
) -> tuple[AdminInvitation, str]:
    """A new invitation. The token is returned once."""
    email = email.lower()
    if _name_in_use(db, church_name):
        raise _church_name_taken()
    if db.scalar(select(Person.id).where(Person.closed_at.is_(None), Person.email == email)):
        raise _account_exists()
    pending = db.scalar(
        select(AdminInvitation.id).where(
            AdminInvitation.accepted_at.is_(None),
            AdminInvitation.cancelled_at.is_(None),
            AdminInvitation.expires_at > datetime.now(UTC),
            AdminInvitation.email == email,
        )
    )
    if pending is not None:
        raise ApiError(409, "invitation_exists", "This address already has an invitation")
    token = new_opaque_token()
    invitation = AdminInvitation(
        email=email,
        church_name=church_name,
        invited_by_id=owner.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.admin_invitation_days),
    )
    db.add(invitation)
    try:
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        raise ApiError(
            409, "state_changed", "The invitation could not be made. Reload and try again."
        ) from None
    return invitation, token


def pending(db: Session, *, limit: int, offset: int) -> tuple[list[ChurchInvitationSummary], int]:
    """The invitations that are not decided (an expired one shows as such until cancelled), one
    page, newest first, and the total."""
    undecided = select(AdminInvitation).where(
        AdminInvitation.accepted_at.is_(None), AdminInvitation.cancelled_at.is_(None)
    )
    total = db.scalar(select(func.count()).select_from(undecided.subquery())) or 0
    rows = db.scalars(
        undecided.order_by(AdminInvitation.created_at.desc(), AdminInvitation.id)
        .limit(limit)
        .offset(offset)
    )
    return [
        ChurchInvitationSummary(
            id=i.id,
            church_name=i.church_name,
            email=i.email or "",
            created_at=i.created_at,
            expires_at=i.expires_at,
            expired=not _live(i),
        )
        for i in rows
    ], total


def cancel(db: Session, invitation_id: uuid.UUID) -> None:
    """Cancel an undecided invitation; the invited address is cleared."""
    invitation = db.get(AdminInvitation, invitation_id, with_for_update=True)
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.cancelled_at is not None
    ):
        raise ApiError(404, "not_found", "There is no such invitation")
    invitation.cancelled_at = datetime.now(UTC)
    invitation.email = None
    db.commit()


def _resolve(db: Session, token: str, *, lock: bool = False) -> AdminInvitation | None:
    query = select(AdminInvitation).where(AdminInvitation.token_hash == hash_token(token))
    found = db.scalar(query.with_for_update() if lock else query)
    return found if found is not None and _live(found) else None


def info(db: Session, token: str) -> AdminInvitationInfo:
    invitation = _resolve(db, token)
    if invitation is None or invitation.email is None:
        raise _not_found()
    return AdminInvitationInfo(
        church_name=invitation.church_name, email_domain=invitation.email.split("@")[-1]
    )


def accept(db: Session, body: AdminInvitationAccept) -> Person:
    """Create the church, its first home group and its ADMIN (who leads the group)."""
    # Hash first: the cost does not tell a good invitation from a bad one.
    password_hash = hash_password(body.password.get_secret_value())
    invitation = _resolve(db, body.token, lock=True)
    if invitation is None or invitation.email is None:
        raise _not_found()
    owner = db.scalar(select(Person).where(Person.status == "owner", Person.closed_at.is_(None)))
    if owner is None:  # cannot happen: there is always one OWNER
        raise _not_found()
    email = invitation.email
    if _name_in_use_by_church(db, invitation.church_name):
        raise _church_name_taken()
    taken = db.scalar(
        select(Person.id).where(
            Person.closed_at.is_(None),
            or_(Person.email == email, Person.mobile_number == body.mobile_number),
        )
    )
    if taken is not None:
        raise _account_exists()
    admin_id, church_id, group_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        # The rows refer to each other; the references are checked at commit.
        db.add(Church(id=church_id, name=invitation.church_name, admin_id=admin_id))
        db.flush()
        db.add(
            HomeGroup(
                id=group_id, church_id=church_id, name=body.home_group_name, leader_id=admin_id
            )
        )
        db.flush()
        admin = Person(
            id=admin_id,
            status="admin",
            church_id=church_id,
            home_group_id=group_id,
            full_name=body.full_name,
            email=email,
            mobile_number=body.mobile_number,
            password_hash=password_hash,
            status_set_by_id=owner.id,
        )
        db.add(admin)
        db.flush()
        db.add(
            StatusChange(
                person_id=admin_id,
                from_status=None,
                to_status="admin",
                changed_by_id=owner.id,
                kind="appoint",
                at=datetime.now(UTC),
            )
        )
        invitation.accepted_at = datetime.now(UTC)
        invitation.email = None  # personal data: gone once decided
        db.add(Notification(person_id=owner.id, kind=CHURCH_CREATED, subject_id=admin_id))
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        # Two acceptances at once, a name or an address taken a moment ago, or a value the
        # database refuses: nothing is half done.
        raise ApiError(
            409, "state_changed", "The invitation could not be accepted. Reload and try again."
        ) from None
    return admin


def _name_in_use_by_church(db: Session, name: str) -> bool:
    return (
        db.scalar(
            select(Church.id).where(
                Church.closed_at.is_(None), func.lower(Church.name) == name.lower()
            )
        )
        is not None
    )
