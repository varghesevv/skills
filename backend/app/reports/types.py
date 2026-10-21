import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

Cell = str | int | float | None


class ReportError(ValueError):
    """A report cannot be produced for the given name or parameters."""


def cell(value: Any) -> Cell:
    """Turn a database value into something JSON, CSV and HTML can all show."""
    if value is None or isinstance(value, str | int | float):
        return value
    if isinstance(value, Decimal):
        return round(float(value), 2)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


@dataclass
class Section:
    title: str
    columns: list[str]
    rows: list[list[Cell]] = field(default_factory=list)


@dataclass
class ReportResult:
    sections: list[Section]

    @property
    def row_count(self) -> int:
        return sum(len(section.rows) for section in self.sections)


@dataclass(frozen=True)
class ReportParams:
    """The window is [start, end) in UTC; days are counted in `timezone`."""

    start: datetime
    end: datetime
    timezone: str
    user_type: str | None = None
    skill: str | None = None
    currency: str | None = None
    min_ratings: int = 1
    org_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ReportDef:
    name: str
    code: str
    title: str
    description: str
    build: Callable[[Session, ReportParams], list[Section]]
    filters: tuple[str, ...] = ()
    org_scoped: bool = False  # organisations may run it, limited to their own data
