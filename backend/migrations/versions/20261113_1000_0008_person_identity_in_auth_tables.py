"""allow the person identity in login history and token tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13 10:00:00
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_TABLES = ("login_history", "password_reset_tokens", "refresh_tokens")
_OLD = "'freelancer', 'workhost', 'organisation', 'admin'"
_NEW = _OLD + ", 'person'"


def _replace(values: str) -> None:
    for table in _TABLES:
        name = op.f(f"ck_{table}_user_type_valid")
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"user_type IN ({values})")


def upgrade() -> None:
    _replace(_NEW)


def downgrade() -> None:
    # Rows of people cannot stay under the narrower rule.
    for table in _TABLES:
        op.execute(f"DELETE FROM {table} WHERE user_type = 'person'")  # noqa: S608
    _replace(_OLD)
