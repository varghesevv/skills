"""A person closes their own account (FR-X-01 to FR-X-03).

The row stays, marked closed, with the personal details cleared; the status history, the vouches
they gave and the ratings stay. They leave their home group without being revoked and nobody they
admitted is flagged. Leaders step down first; the OWNER hands over. Same flow as the in-app
"delete account" the app stores require.
"""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import verify_dummy, verify_password
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from app.models.church import Person
from app.models.trust import GroupInvitation, VouchLink


def close_account(db: Session, person: Person, password: str) -> None:
    # Hold the row: a leader acting on this person at the same moment waits for us.
    db.refresh(person, with_for_update=True)
    if person.password_hash is None or not verify_password(person.password_hash, password):
        verify_dummy(password)
        raise ApiError(403, "invalid_password", "The password is not correct")
    if person.status == "verifier":
        raise ApiError(409, "leads_a_group", "Step down as leader of your home group first")
    if person.status in ("admin", "owner"):
        raise ApiError(409, "leads_a_church", "Hand over your role first")
    if person.status == "revoked" or person.closed_at is not None:
        raise ApiError(403, "account_revoked", "This account cannot be closed")
    now = datetime.now(UTC)
    email = person.email
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
            .where(LoginHistory.login_email == email)
            .values(login_email=None, ip_address=None, user_agent=None)
        )
    db.commit()
