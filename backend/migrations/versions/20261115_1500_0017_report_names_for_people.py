"""the daily report is about sign-ups of people (S5.3)

`users_registered_daily` becomes `signups_daily`. Rows of `report_runs` keep the name they were
made under.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-15 15:00:00
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE report_schedules SET report_name = 'signups_daily' "
        "WHERE report_name = 'users_registered_daily'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE report_schedules SET report_name = 'users_registered_daily' "
        "WHERE report_name = 'signups_daily'"
    )
