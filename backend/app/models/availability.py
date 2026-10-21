import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class FreelancerUnavailability(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "freelancer_unavailability"

    freelancer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("freelancers.id", ondelete="CASCADE")
    )
    unavailable_from: Mapped[datetime]
    unavailable_to: Mapped[datetime]

    __table_args__ = (
        CheckConstraint("unavailable_from < unavailable_to", name="range_valid"),
        # One freelancer cannot have two overlapping unavailability periods (needs btree_gist).
        ExcludeConstraint(
            ("freelancer_id", "="),
            (text("tstzrange(unavailable_from, unavailable_to)"), "&&"),
            using="gist",
            name="ex_freelancer_unavailability_no_overlap",
        ),
    )
