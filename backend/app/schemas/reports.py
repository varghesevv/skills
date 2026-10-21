import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class ReportInfo(BaseModel):
    name: str
    code: str
    title: str
    description: str
    filters: list[str]


class ReportRunOut(BaseModel):
    id: uuid.UUID
    report_name: str
    window_from: datetime
    window_to: datetime
    started_at: datetime
    finished_at: datetime | None
    status: str
    row_count: int | None
    error_message: str | None
    has_files: bool


class RunRequest(BaseModel):
    """Whole days in the report time zone, both included."""

    date_from: date
    date_to: date


class ScheduleOut(BaseModel):
    report_name: str
    cron_expression: str
    timezone: str
    is_enabled: bool


class ScheduleUpdate(BaseModel):
    cron_expression: Annotated[str, Field(min_length=9, max_length=100)]  # for example "5 0 * * *"
    timezone: Annotated[str, Field(min_length=1, max_length=64)]
    is_enabled: bool = True
