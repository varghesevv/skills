"""seed labels and report schedules

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 23:35:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LABELS: dict[str, list[str]] = {
    "skill": ["plumbing", "electrical", "networking", "patientcare", "assistance"],
    # 08-06 is assumed to mean 08:00 to 18:00 (open question Q2).
    "timing": ["06-12", "08-06", "20-24", "24h"],
    "language": ["English", "Hindi", "Tamil"],
    "nativity": ["Indian", "Srilankan", "Keralite", "Bangla", "Philippines"],
    "skill_level": ["basic", "50%", "80%"],
}

# Times are in the schedule's own timezone (default Asia/Dubai).
REPORT_SCHEDULES = [
    ("users_registered_daily", "5 0 * * *"),
    ("weekly_summary", "0 6 * * 1"),
    ("monthly_summary", "0 6 1 * *"),
]

labels = sa.table("labels", sa.column("label_name", sa.String), sa.column("label_type", sa.String))
report_schedules = sa.table(
    "report_schedules", sa.column("report_name", sa.String), sa.column("cron_expression", sa.String)
)


def upgrade() -> None:
    op.bulk_insert(
        labels,
        [
            {"label_name": name, "label_type": label_type}
            for label_type, names in LABELS.items()
            for name in names
        ],
    )
    op.bulk_insert(
        report_schedules,
        [{"report_name": name, "cron_expression": cron} for name, cron in REPORT_SCHEDULES],
    )


def downgrade() -> None:
    for name, _ in REPORT_SCHEDULES:
        op.execute(sa.delete(report_schedules).where(report_schedules.c.report_name == name))
    for label_type, names in LABELS.items():
        op.execute(
            sa.delete(labels).where(
                labels.c.label_type == label_type, labels.c.label_name.in_(names)
            )
        )
