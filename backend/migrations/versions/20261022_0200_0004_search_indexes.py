"""search indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22 02:00:00
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_freelancers_rate_currency"), "freelancers", ["rate_currency", "rate_per_hour"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_freelancers_rate_currency"), table_name="freelancers")
