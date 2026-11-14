"""an index on the time of a phone number view, for the OWNER's list and the retention

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-14 11:00:00
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_contact_views_viewed_at"), "contact_views", ["viewed_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contact_views_viewed_at"), table_name="contact_views")
