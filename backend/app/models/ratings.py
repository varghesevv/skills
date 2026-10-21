import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class UserRating(UUIDPrimaryKeyMixin, Base):
    """A work host's rating (1 to 10) of a freelancer. One rating per pair, editable."""

    __tablename__ = "user_ratings"

    work_host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_hosts.id", ondelete="CASCADE"))
    freelancer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("freelancers.id", ondelete="CASCADE")
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    rated_on: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("work_host_id", "freelancer_id", name="host_freelancer"),
        CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
        Index(None, "freelancer_id"),
    )
