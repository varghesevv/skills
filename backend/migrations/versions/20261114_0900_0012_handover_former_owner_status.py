"""the outgoing OWNER's status after a handover is chosen when it is proposed

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-14 09:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "handover_requests",
        sa.Column(
            "former_owner_status",
            sa.String(length=20),
            server_default="provider",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_handover_requests_former_owner_status_valid"),
        "handover_requests",
        "former_owner_status IN ('provider', 'searcher')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_handover_requests_former_owner_status_valid"), "handover_requests", type_="check"
    )
    op.drop_column("handover_requests", "former_owner_status")
