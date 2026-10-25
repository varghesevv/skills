import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import REVEAL_CHANNELS, REVEAL_SOURCES, sql_in


class PhoneReveal(UUIDPrimaryKeyMixin, Base):
    """One time a work host asked to see a freelancer's mobile number.

    The number itself is never stored here. Rows are kept for reports and for rate limiting.
    `channel` and `source` are hints sent by the web app, not facts the server can check.
    """

    __tablename__ = "phone_reveals"

    work_host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_hosts.id", ondelete="CASCADE"))
    freelancer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("freelancers.id", ondelete="CASCADE")
    )
    revealed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    channel: Mapped[str] = mapped_column(String(10))  # dial (phone) or show (desktop)
    source: Mapped[str] = mapped_column(String(10))  # search or detail
    searched_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))

    __table_args__ = (
        CheckConstraint(sql_in("channel", REVEAL_CHANNELS), name="channel_valid"),
        CheckConstraint(sql_in("source", REVEAL_SOURCES), name="source_valid"),
        Index("ix_phone_reveals_host_time", "work_host_id", "revealed_at"),
        Index(None, "freelancer_id"),
        Index(None, "revealed_at"),
    )
