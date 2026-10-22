"""full name for freelancers and work hosts

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22 03:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = ("freelancers", "work_hosts")


def upgrade() -> None:
    # Nullable: accounts created before this change have no name. Registration requires one.
    for table in TABLES:
        op.add_column(table, sa.Column("full_name", sa.String(length=200), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "full_name")
