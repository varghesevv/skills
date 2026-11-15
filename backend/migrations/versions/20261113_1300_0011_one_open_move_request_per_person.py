"""a person has at most one open move request

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-13 13:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_move_requests_one_open",
        "move_requests",
        ["person_id"],
        unique=True,
        postgresql_where=sa.text("completed_at IS NULL AND cancelled_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_move_requests_one_open", table_name="move_requests")
