"""The church trust model: churches, home groups and the people in them.

Rules the columns and constraints here carry (see docs/specification/03-data-model.md and
docs/verification.md): exactly one open OWNER, one ADMIN per open church, one leader per open
home group, every open non-revoked person in a home group of their own church. The "exactly one"
rules that must only hold at the end of a transaction are deferrable exclusion constraints and
constraint triggers created by migration 0007 (Alembic does not model those).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import REQUESTED_STATUSES, STATUSES, sql_in


class Church(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "churches"

    name: Mapped[str] = mapped_column(String(200))
    # The ADMIN, or the OWNER in the OWNER's own church. Checked at commit (circular reference).
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", deferrable=True, initially="DEFERRED", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index(
            "uq_churches_open_name",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )


class HomeGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "home_groups"

    church_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("churches.id"))
    name: Mapped[str] = mapped_column(String(200))
    # Always set while the group is open; a closed group keeps its last leader as history.
    leader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", deferrable=True, initially="DEFERRED", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("id", "church_id"),  # target of the composite key on people
        Index(
            "uq_home_groups_open_name",
            "church_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        Index(None, "church_id"),
    )


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One account and one status per person (ADR-0017)."""

    __tablename__ = "people"

    status: Mapped[str] = mapped_column(String(20))
    church_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("churches.id"))
    # NULL if and only if the person is revoked or the account is closed.
    home_group_id: Mapped[uuid.UUID | None] = mapped_column()
    last_home_group_id: Mapped[uuid.UUID | None] = mapped_column()

    # Personal details; all NULL once the account is closed.
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    mobile_number: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(Text)

    requested_status: Mapped[str | None] = mapped_column(String(20))
    status_set_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    flagged_for_recheck: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    # Provider profile.
    whatsapp_availability: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    nationality: Mapped[str | None] = mapped_column(String(100))
    primary_language: Mapped[str | None] = mapped_column(String(100))
    rate_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rate_currency: Mapped[str | None] = mapped_column(String(3))
    is_rate_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    last_login_at: Mapped[datetime | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        ForeignKeyConstraint(
            ["home_group_id", "church_id"],
            ["home_groups.id", "home_groups.church_id"],
            name="fk_people_home_group_id_home_groups",
        ),
        # A revoked person stays on their church's list: the group they were removed from is in it.
        ForeignKeyConstraint(
            ["last_home_group_id", "church_id"],
            ["home_groups.id", "home_groups.church_id"],
            name="fk_people_last_home_group_id_home_groups",
        ),
        CheckConstraint(sql_in("status", STATUSES), name="status_valid"),
        CheckConstraint(
            "requested_status IS NULL OR " + sql_in("requested_status", REQUESTED_STATUSES),
            name="requested_status_valid",
        ),
        CheckConstraint(
            "(home_group_id IS NULL) = (status = 'revoked' OR closed_at IS NOT NULL)",
            name="group_matches_status",
        ),
        CheckConstraint(
            "closed_at IS NOT NULL OR (full_name IS NOT NULL AND email IS NOT NULL "
            "AND mobile_number IS NOT NULL AND password_hash IS NOT NULL)",
            name="open_has_details",
        ),
        CheckConstraint(
            "closed_at IS NULL OR (full_name IS NULL AND email IS NULL "
            "AND mobile_number IS NULL AND password_hash IS NULL)",
            name="closed_has_no_details",
        ),
        CheckConstraint("email IS NULL OR email = lower(email)", name="email_lowercase"),
        CheckConstraint("full_name IS NULL OR char_length(full_name) >= 2", name="name_length"),
        CheckConstraint("rate_per_hour IS NULL OR rate_per_hour >= 0", name="rate_non_negative"),
        CheckConstraint(
            "rate_currency IS NULL OR rate_currency ~ '^[A-Z]{3}$'", name="currency_iso"
        ),
        CheckConstraint(
            "(rate_per_hour IS NULL) = (rate_currency IS NULL)", name="rate_with_currency"
        ),
        # Open accounts are unique by email and by mobile number across the installation;
        # revoked accounts count as open, which stops a revoked person signing up again.
        Index(
            "uq_people_open_email",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        Index(
            "uq_people_open_mobile",
            "mobile_number",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        Index(None, "church_id", "status"),
        Index(None, "home_group_id", "status"),
        Index(None, "last_home_group_id"),
        Index(None, "status_set_by_id"),
        Index(None, "created_at"),
        Index(
            "ix_people_providers",
            "created_at",
            postgresql_where=text(
                "status IN ('provider', 'verifier', 'admin', 'owner') AND closed_at IS NULL"
            ),
        ),
    )
