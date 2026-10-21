import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import USER_TYPES, sql_in


class LoginHistory(UUIDPrimaryKeyMixin, Base):
    """Every login attempt, successful or not. user_id is empty for unknown emails."""

    __tablename__ = "login_history"

    user_type: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID | None]
    login_email: Mapped[str] = mapped_column(String(320))
    login_time: Mapped[datetime] = mapped_column(server_default=func.now())
    succeeded: Mapped[bool] = mapped_column(Boolean)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        CheckConstraint(sql_in("user_type", USER_TYPES), name="user_type_valid"),
        Index(None, "login_time"),
        Index("ix_login_history_email_time", "login_email", "login_time"),
    )


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    """One-time password reset token. Only a hash of the token is stored."""

    __tablename__ = "password_reset_tokens"

    user_type: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID]
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("user_type", USER_TYPES), name="user_type_valid"),
        Index("ix_password_reset_tokens_user", "user_type", "user_id"),
    )


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    """Rotating refresh token. Only a hash of the token is stored."""

    __tablename__ = "refresh_tokens"

    user_type: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID]
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(sql_in("user_type", USER_TYPES), name="user_type_valid"),
        Index("ix_refresh_tokens_user", "user_type", "user_id"),
    )
