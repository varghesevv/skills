from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import REPORT_RUN_STATUSES, sql_in


class ReportSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_schedules"

    report_name: Mapped[str] = mapped_column(String(100), unique=True)
    cron_expression: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Dubai", server_default="Asia/Dubai"
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    recipients: Mapped[str] = mapped_column(Text, default="", server_default="")


class ReportRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_runs"

    report_name: Mapped[str] = mapped_column(String(100))
    window_from: Mapped[datetime]
    window_to: Mapped[datetime]
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(20), default="running", server_default="running")
    file_path: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # The same report for the same window never runs twice (idempotency).
        UniqueConstraint("report_name", "window_from", "window_to", name="window"),
        CheckConstraint(sql_in("status", REPORT_RUN_STATUSES), name="status_valid"),
    )
