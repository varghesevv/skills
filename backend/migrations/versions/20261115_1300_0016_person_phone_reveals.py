"""the record of mobile number reveals between people (S5.2b)

Named `person_phone_reveals` until slice S5.3 drops the older `phone_reveals` (which the reports
still read) and gives this table the name of the data model (decision D-43).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-15 13:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person_phone_reveals",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "revealer_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "revealed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("searched_skills", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.CheckConstraint("channel IN ('dial', 'show')", name="channel_valid"),
        sa.CheckConstraint("source IN ('search', 'detail')", name="source_valid"),
        sa.CheckConstraint("revealer_id <> provider_id", name="not_self"),
    )
    op.create_index(
        "ix_person_phone_reveals_revealer_time",
        "person_phone_reveals",
        ["revealer_id", "revealed_at"],
    )
    op.create_index(
        op.f("ix_person_phone_reveals_provider_id"), "person_phone_reveals", ["provider_id"]
    )
    op.create_index(
        op.f("ix_person_phone_reveals_revealed_at"), "person_phone_reveals", ["revealed_at"]
    )


def downgrade() -> None:
    op.drop_table("person_phone_reveals")
