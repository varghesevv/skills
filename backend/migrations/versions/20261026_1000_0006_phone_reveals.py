"""phone reveal log

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-26 10:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phone_reveals",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "work_host_id",
            sa.Uuid(),
            sa.ForeignKey("work_hosts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "freelancer_id",
            sa.Uuid(),
            sa.ForeignKey("freelancers.id", ondelete="CASCADE"),
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
    )
    op.create_index("ix_phone_reveals_host_time", "phone_reveals", ["work_host_id", "revealed_at"])
    op.create_index(op.f("ix_phone_reveals_freelancer_id"), "phone_reveals", ["freelancer_id"])
    op.create_index(op.f("ix_phone_reveals_revealed_at"), "phone_reveals", ["revealed_at"])


def downgrade() -> None:
    op.drop_table("phone_reveals")
