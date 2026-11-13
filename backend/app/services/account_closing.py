"""A person closes their own account (FR-X-01 to FR-X-03).

The row stays, marked closed, with the personal details cleared; the status history, the vouches
they gave and the ratings stay. They leave their home group without being revoked and nobody they
admitted is flagged. Leaders step down first; the OWNER hands over. Same flow as the in-app
"delete account" the app stores require.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import verify_dummy, verify_password
from app.models.auth import LoginHistory, PasswordResetToken, RefreshToken
from app.models.church import Person
from app.models.trust import GroupInvitation, VouchLink
from app.services.auth import check_throttle, clean_ip, record_attempt

# The statements of `clear_accounts` take one parameter per person; PostgreSQL allows 65535, so a
# very large church is cleared in slices.
CHUNK = 1000


def _slices(items: list[Any]) -> list[list[Any]]:
    return [items[i : i + CHUNK] for i in range(0, len(items), CHUNK)]


def clear_accounts(db: Session, people: list[Person], now: datetime) -> None:
    """Mark the accounts closed and clear what identifies the people. The caller commits.

    Used when people leave, when a leader declines an application and when a church closes: the
    rows, the history and the vouches given stay, and nothing of theirs works any more. A closing
    church has many people, so everything beyond the rows themselves is done in a few statements.
    """
    if not people:
        return
    ids = [p.id for p in people]
    emails = [p.email.lower() for p in people if p.email]  # read before they are cleared
    for person in people:
        person.closed_at = now
        person.home_group_id = None
        person.full_name = person.email = person.mobile_number = person.password_hash = None
        person.flagged_for_recheck = False
    # No session, reset link or invitation of theirs works any more, and the address, the
    # network address and the browser of their login attempts are forgotten.
    for chunk in _slices(ids):
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_type == "person",
                RefreshToken.user_id.in_(chunk),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_type == "person",
                PasswordResetToken.user_id.in_(chunk),
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        db.execute(
            update(VouchLink)
            .where(VouchLink.person_id.in_(chunk), VouchLink.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.execute(
            update(GroupInvitation)
            .where(GroupInvitation.created_by_id.in_(chunk), GroupInvitation.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.execute(
            update(LoginHistory)
            .where(LoginHistory.user_type == "person", LoginHistory.user_id.in_(chunk))
            .values(login_email=None, ip_address=None, user_agent=None)
        )
    for chunk in _slices(
        emails
    ):  # attempts before the person was recognised carry only the address
        db.execute(
            update(LoginHistory)
            .where(
                LoginHistory.user_type == "person",  # an older account keeps its own trail
                func.lower(LoginHistory.login_email).in_(chunk),
            )
            .values(login_email=None, ip_address=None, user_agent=None)
        )


def clear_account(db: Session, person: Person, now: datetime) -> None:
    """Close one account (see `clear_accounts`)."""
    clear_accounts(db, [person], now)


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
    clear_account(db, person, now)
    db.commit()
