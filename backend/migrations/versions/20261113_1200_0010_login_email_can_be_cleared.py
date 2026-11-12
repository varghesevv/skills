"""the email of a login attempt can be cleared when the person closes their account

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-13 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("login_history", "login_email", existing_type=sa.String(320), nullable=True)


def downgrade() -> None:
    # Rows whose email was cleared cannot stay under the stricter rule.
    history = sa.table("login_history", sa.column("login_email"))
    op.execute(sa.delete(history).where(history.c.login_email.is_(None)))
    op.alter_column("login_history", "login_email", existing_type=sa.String(320), nullable=False)
