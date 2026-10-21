"""organisation approval status

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 01:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organisations",
        sa.Column("approval_status", sa.String(20), server_default="pending", nullable=False),
    )
    op.add_column("organisations", sa.Column("approved_at", sa.DateTime(timezone=True)))
    op.add_column("organisations", sa.Column("approved_by_admin_id", sa.Uuid()))
    op.create_check_constraint(
        "approval_status_valid",
        "organisations",
        "approval_status IN ('pending', 'approved', 'rejected')",
    )
    op.create_foreign_key(
        "fk_organisations_approved_by_admin_id_admins",
        "organisations",
        "admins",
        ["approved_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_organisations_approval_status"), "organisations", ["approval_status"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organisations_approval_status"), table_name="organisations")
    op.drop_constraint(
        "fk_organisations_approved_by_admin_id_admins", "organisations", type_="foreignkey"
    )
    op.drop_constraint("ck_organisations_approval_status_valid", "organisations", type_="check")
    op.drop_column("organisations", "approved_by_admin_id")
    op.drop_column("organisations", "approved_at")
    op.drop_column("organisations", "approval_status")
