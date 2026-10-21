import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import VOUCH_STATUSES, sql_in


class OrgFreelancer(Base):
    """An organisation vouching for a freelancer. Starts as pending until the freelancer accepts."""

    __tablename__ = "org_freelancers"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    freelancer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("freelancers.id", ondelete="CASCADE"), primary_key=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("status", VOUCH_STATUSES), name="status_valid"),
        Index(None, "freelancer_id"),
    )
