import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import APPROVAL_STATUSES, sql_in


class AccountMixin:
    """Columns shared by every kind of login account."""

    user_email: Mapped[str] = mapped_column(String(320), unique=True)
    mobile_number: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(Text)
    last_login_at: Mapped[datetime | None] = mapped_column()


def _email_is_lowercase() -> CheckConstraint:
    # Emails are stored lowercase so the plain unique constraint is case-insensitive.
    return CheckConstraint("user_email = lower(user_email)", name="email_lowercase")


class WorkHost(UUIDPrimaryKeyMixin, AccountMixin, TimestampMixin, Base):
    __tablename__ = "work_hosts"

    # Required when registering; empty only for accounts created before names existed.
    full_name: Mapped[str | None] = mapped_column(String(200))

    avail_sun: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_mon: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_tue: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_wed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_thu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_fri: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    avail_sat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    __table_args__ = (_email_is_lowercase(), Index(None, "created_at"))


class Freelancer(UUIDPrimaryKeyMixin, AccountMixin, TimestampMixin, Base):
    __tablename__ = "freelancers"

    # Required when registering; empty only for accounts created before names existed.
    full_name: Mapped[str | None] = mapped_column(String(200))

    whatsapp_availability: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    nationality: Mapped[str | None] = mapped_column(String(100))
    primary_language: Mapped[str | None] = mapped_column(String(100))
    rate_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rate_currency: Mapped[str | None] = mapped_column(String(3))
    is_rate_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    __table_args__ = (
        _email_is_lowercase(),
        CheckConstraint("rate_per_hour IS NULL OR rate_per_hour >= 0", name="rate_non_negative"),
        CheckConstraint(
            "rate_currency IS NULL OR rate_currency ~ '^[A-Z]{3}$'", name="currency_iso"
        ),
        CheckConstraint(
            "(rate_per_hour IS NULL) = (rate_currency IS NULL)", name="rate_with_currency"
        ),
        Index(None, "created_at"),
        Index(None, "rate_currency", "rate_per_hour"),  # search: maximum rate in a currency
    )


class Organisation(UUIDPrimaryKeyMixin, AccountMixin, TimestampMixin, Base):
    __tablename__ = "organisations"

    org_name: Mapped[str] = mapped_column(String(200))
    # An organisation cannot log in until an admin approves it.
    approval_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    approved_at: Mapped[datetime | None] = mapped_column()
    approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL")
    )

    __table_args__ = (
        _email_is_lowercase(),
        CheckConstraint(sql_in("approval_status", APPROVAL_STATUSES), name="approval_status_valid"),
        Index(None, "created_at"),
        Index(None, "approval_status"),
    )


class Admin(UUIDPrimaryKeyMixin, AccountMixin, TimestampMixin, Base):
    """Platform operator. Created by a CLI command, never through self-registration."""

    __tablename__ = "admins"

    __table_args__ = (_email_is_lowercase(), Index(None, "created_at"))
