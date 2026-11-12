"""allow the person identity in login history and token tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# login_history grows with every login attempt, so the new rule is added NOT VALID (a short lock)
# and checked afterwards (a lock that does not block reads and writes).
_TABLES = ("login_history", "password_reset_tokens", "refresh_tokens")
_OLD = "'freelancer', 'workhost', 'organisation', 'admin'"
_NEW = _OLD + ", 'person'"


def _replace(values: str) -> None:
    for table in _TABLES:
        name = op.f(f"ck_{table}_user_type_valid")
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(
            name, table, f"user_type IN ({values})", postgresql_not_valid=True
        )
        op.execute(sa.text(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}"))  # noqa: S608


def upgrade() -> None:
    _replace(_NEW)


def downgrade() -> None:
    # Rows of people cannot stay under the narrower rule.
    for table in _TABLES:
        rows = sa.table(table, sa.column("user_type"))
        op.execute(sa.delete(rows).where(rows.c.user_type == "person"))
    _replace(_OLD)
