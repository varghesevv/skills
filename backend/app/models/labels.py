import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import LABEL_TYPES, sql_in


class Label(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "labels"

    label_name: Mapped[str] = mapped_column(String(100))
    label_type: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    __table_args__ = (
        UniqueConstraint("label_type", "label_name", name="type_name"),
        CheckConstraint(sql_in("label_type", LABEL_TYPES), name="label_type_valid"),
    )


class FreelancerLabel(Base):
    """A label chosen by a freelancer. For skills, level_label_id holds the skill level.

    A database trigger (see migration 0001) guarantees that level_label_id is only set on
    skill labels and always points at a skill_level label.
    """

    __tablename__ = "freelancer_labels"

    freelancer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("freelancers.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("labels.id", ondelete="RESTRICT"), primary_key=True
    )
    level_label_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("labels.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        CheckConstraint(
            "level_label_id IS NULL OR level_label_id <> label_id", name="level_differs"
        ),
        Index(None, "label_id"),
    )
