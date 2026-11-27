"""people who must change a temporary password before using the app

Revision ID: 0022
Revises: 0021

The people created from the initial config (story S100) are given a temporary password from that
file. The flag makes them choose their own the first time they sign in.
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "people",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("people", "must_change_password")
