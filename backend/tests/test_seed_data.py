import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Label, ReportSchedule

pytestmark = pytest.mark.db

EXPECTED_LABEL_COUNTS = {
    "skill": 5,
    "timing": 4,
    "language": 3,
    "nativity": 5,
    "skill_level": 3,
}


def test_labels_are_seeded(session: Session) -> None:
    rows = session.execute(select(Label.label_type, func.count()).group_by(Label.label_type)).all()
    assert dict(rows) == EXPECTED_LABEL_COUNTS


def test_report_schedules_are_seeded(session: Session) -> None:
    names = set(session.scalars(select(ReportSchedule.report_name)))
    assert {"users_registered_daily", "weekly_summary", "monthly_summary"} <= names
    daily = session.scalars(
        select(ReportSchedule).where(ReportSchedule.report_name == "users_registered_daily")
    ).one()
    assert daily.cron_expression == "5 0 * * *"
    assert daily.timezone == "Asia/Dubai"
    assert daily.is_enabled is True
