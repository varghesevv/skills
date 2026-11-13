"""Vouching, status history, requests and notifications of the church trust model."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import GROUP_REQUEST_STATES, STATUS_CHANGE_KINDS, STATUSES, sql_in


class StatusChange(UUIDPrimaryKeyMixin, Base):
    """Permanent, append-only history; the chain of trust is built from it."""

    __tablename__ = "status_changes"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))  # NULL at account creation
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    kind: Mapped[str] = mapped_column(String(20))
    at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("kind", STATUS_CHANGE_KINDS), name="kind_valid"),
        CheckConstraint(
            "from_status IS NULL OR " + sql_in("from_status", STATUSES), name="from_status_valid"
        ),
        CheckConstraint(sql_in("to_status", STATUSES), name="to_status_valid"),
        # Only a signup or an operator change in the database has no acting person.
        CheckConstraint(
            "(changed_by_id IS NULL) = (kind IN ('signup', 'operator'))", name="actor_matches_kind"
        ),
        # Nobody changes their own status, except the OWNER in a handover.
        CheckConstraint(
            "changed_by_id IS DISTINCT FROM person_id OR kind = 'handover'", name="not_self"
        ),
        Index("ix_status_changes_person_at", "person_id", "at"),
        Index(None, "changed_by_id"),
    )


class Vouch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vouches"

    applicant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    voucher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("applicant_id", "voucher_id"),
        CheckConstraint("applicant_id <> voucher_id", name="not_self"),
        Index(None, "voucher_id"),
    )


class VouchLink(UUIDPrimaryKeyMixin, Base):
    """The link an applicant shares with people who know them. Only a hash is stored."""

    __tablename__ = "vouch_links"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index(None, "person_id"),)


class GroupInvitation(UUIDPrimaryKeyMixin, Base):
    """The link a leader shares to bring people into their home group."""

    __tablename__ = "group_invitations"

    home_group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("home_groups.id"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index(None, "home_group_id"), Index(None, "created_by_id"))


class GroupRequest(UUIDPrimaryKeyMixin, Base):
    """A member asking to start a home group."""

    __tablename__ = "group_requests"

    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    church_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("churches.id"))
    group_name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    decided_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("state", GROUP_REQUEST_STATES), name="state_valid"),
        CheckConstraint(
            "(state = 'open') = (decided_at IS NULL AND decided_by_id IS NULL)",
            name="decision_matches_state",
        ),
        Index(
            "uq_group_requests_one_open",
            "requester_id",
            unique=True,
            postgresql_where=text("state = 'open'"),
        ),
        Index(None, "church_id"),
        Index(None, "decided_by_id"),
    )


class AdminInvitation(UUIDPrimaryKeyMixin, Base):
    """The only invitation that creates a church: the church exists once it is accepted."""

    __tablename__ = "admin_invitations"

    email: Mapped[str | None] = mapped_column(String(320))  # cleared when accepted or cancelled
    church_name: Mapped[str] = mapped_column(String(200))
    invited_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "NOT (accepted_at IS NOT NULL AND cancelled_at IS NOT NULL)", name="one_outcome"
        ),
        # The invited address is personal data: gone once the invitation is decided.
        CheckConstraint(
            "email IS NULL OR (accepted_at IS NULL AND cancelled_at IS NULL)",
            name="email_cleared_when_decided",
        ),
        Index(None, "invited_by_id"),
    )


class HandoverRequest(UUIDPrimaryKeyMixin, Base):
    """The OWNER proposes, the chosen ADMIN accepts; everything happens in one step."""

    __tablename__ = "handover_requests"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    new_owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    successor_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    successor_leader_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    # What the outgoing OWNER becomes when they keep neither role (PROVIDER or SEARCHER).
    former_owner_status: Mapped[str] = mapped_column(
        String(20), default="provider", server_default="provider"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("owner_id <> new_owner_id", name="different_people"),
        CheckConstraint(
            "former_owner_status IN ('provider', 'searcher')", name="former_owner_status_valid"
        ),
        CheckConstraint(
            "NOT (accepted_at IS NOT NULL AND cancelled_at IS NOT NULL)", name="one_outcome"
        ),
        Index(
            "uq_handover_requests_one_open",
            "owner_id",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND cancelled_at IS NULL"),
        ),
        Index(None, "new_owner_id"),
        Index(None, "successor_admin_id"),
        Index(None, "successor_leader_id"),
    )


class MoveRequest(UUIDPrimaryKeyMixin, Base):
    """A move between groups of one church; it happens when all three agree."""

    __tablename__ = "move_requests"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    from_group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("home_groups.id"))
    to_group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("home_groups.id"))
    agreed_by_person_at: Mapped[datetime | None] = mapped_column()
    agreed_by_from_leader_at: Mapped[datetime | None] = mapped_column()
    agreed_by_to_leader_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("from_group_id <> to_group_id", name="different_groups"),
        CheckConstraint(
            "NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL)", name="one_outcome"
        ),
        Index(None, "person_id"),
        Index(None, "from_group_id"),
        Index(None, "to_group_id"),
        # A person has at most one open request.
        Index(
            "uq_move_requests_one_open",
            "person_id",
            unique=True,
            postgresql_where=text("completed_at IS NULL AND cancelled_at IS NULL"),
        ),
    )


class Notification(UUIDPrimaryKeyMixin, Base):
    """An in-app notification. It names no person and holds no number; only ids."""

    __tablename__ = "notifications"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    kind: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index("ix_notifications_person_read_created", "person_id", "read_at", "created_at"),
    )


class ContactView(UUIDPrimaryKeyMixin, Base):
    """One row each time a verifier screen shows a person's mobile number (never the number)."""

    __tablename__ = "contact_views"

    viewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    screen: Mapped[str] = mapped_column(String(50))
    viewed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index(None, "viewer_id", "viewed_at"), Index(None, "person_id"))
