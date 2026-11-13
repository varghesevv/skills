"""A person closes their own account (FR-X-01 to FR-X-03).

The row stays, marked closed, with the personal details cleared; the status history, the vouches
they gave and the ratings stay. They leave their home group without being revoked and nobody they
admitted is flagged. Leaders step down first; the OWNER hands over. Same flow as the in-app
"delete account" the app stores require.
"""

from datetime import UTC, datetime

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import verify_dummy, verify_password
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from app.models.church import Person
from app.models.trust import GroupInvitation, VouchLink
from app.services.auth import check_throttle, clean_ip, record_attempt


def clear_account(db: Session, person: Person, now: datetime, email: str) -> None:
    """Mark the account closed and clear what identifies the person. The caller commits.

    Used when people leave and when a leader declines an application: the row, the history and
    the vouches given stay, and nothing of theirs works any more."""
    person.closed_at = now
    person.home_group_id = None
    person.full_name = person.email = person.mobile_number = person.password_hash = None
    person.flagged_for_recheck = False
    # No session, reset link or invitation of theirs works any more, and the address, the
    # network address and the browser of their login attempts are forgotten.
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_type == "person",
            RefreshToken.user_id == person.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_type == "person",
            PasswordResetToken.user_id == person.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.execute(
        update(VouchLink)
        .where(VouchLink.person_id == person.id, VouchLink.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(GroupInvitation)
        .where(GroupInvitation.created_by_id == person.id, GroupInvitation.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(LoginHistory)
        .where(LoginHistory.user_type == "person", LoginHistory.user_id == person.id)
        .values(login_email=None, ip_address=None, user_agent=None)
    )
    if email:  # attempts before the person was recognised carry only the address
        db.execute(
            update(LoginHistory)
            .where(
                LoginHistory.user_type == "person",  # an older account keeps its own trail
                func.lower(LoginHistory.login_email) == email.lower(),
            )
            .values(login_email=None, ip_address=None, user_agent=None)
        )


def close_account(
    db: Session,
    settings: Settings,
    person: Person,
    password: str,
    *,
    ip: str | None,
    user_agent: str | None,
) -> None:
    # Hold the row: a leader acting on this person at the same moment waits for us.
    db.refresh(person, with_for_update=True)
    if person.closed_at is not None or person.status == "revoked":
        raise ApiError(403, "account_revoked", "This account cannot be closed")
    email = person.email or ""
    ip = clean_ip(ip)
    now = datetime.now(UTC)
    # The password is asked again, so a stolen access token must not let anyone guess it: the
    # same throttle as login counts the failures (per address and network address).
    check_throttle(db, settings, user_type="person", email=email, ip=ip, now=now)
    if person.password_hash is None:
        verify_dummy(password)  # not reachable for an open account, but costs the same
    if person.password_hash is None or not verify_password(person.password_hash, password):
        record_attempt(
            db,
            user_type="person",
            user_id=person.id,
            email=email,
            succeeded=False,
            ip=ip,
            user_agent=user_agent,
        )
        db.commit()  # the failure must be counted although the request fails
        raise ApiError(403, "invalid_password", "The password is not correct")
    if person.status == "verifier":
        raise ApiError(409, "leads_a_group", "Step down as leader of your home group first")
    if person.status in ("admin", "owner"):
        raise ApiError(409, "leads_a_church", "Hand over your role first")
    clear_account(db, person, now, email)
    db.commit()
