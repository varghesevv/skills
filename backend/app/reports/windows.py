"""Report time windows. Days are counted in the report time zone; windows are [start, end)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.reports.types import ReportError

MAX_WINDOW_DAYS = 366


def zone_of(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - ZoneInfoNotFoundError, ValueError and friends
        raise ReportError("Unknown time zone") from None


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    """Midnight at the start of `day` in `zone`, as a UTC time."""
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)


def window_from_dates(first: date, last: date, timezone: str) -> tuple[datetime, datetime]:
    """Whole days from `first` to `last`, both included."""
    if last < first:
        raise ReportError("The end date must not be before the start date")
    if (last - first).days + 1 > MAX_WINDOW_DAYS:
        raise ReportError(f"A report window is at most {MAX_WINDOW_DAYS} days")
    zone = zone_of(timezone)
    return local_midnight(first, zone), local_midnight(last + timedelta(days=1), zone)


def default_window(now: datetime, timezone: str, days: int = 30) -> tuple[datetime, datetime]:
    """The last `days` complete days."""
    zone = zone_of(timezone)
    today = now.astimezone(zone).date()
    return local_midnight(today - timedelta(days=days), zone), local_midnight(today, zone)


def scheduled_window(name: str, now: datetime, timezone: str) -> tuple[datetime, datetime]:
    """The most recent complete window for a scheduled report, as of `now`."""
    zone = zone_of(timezone)
    today = now.astimezone(zone).date()
    if name == "weekly_summary":  # the previous Monday to Sunday
        monday = today - timedelta(days=today.weekday())
        return local_midnight(monday - timedelta(days=7), zone), local_midnight(monday, zone)
    if name == "monthly_summary":  # the previous calendar month
        first = today.replace(day=1)
        previous_first = (first - timedelta(days=1)).replace(day=1)
        return local_midnight(previous_first, zone), local_midnight(first, zone)
    # users_registered_daily and any other scheduled report: yesterday
    return local_midnight(today - timedelta(days=1), zone), local_midnight(today, zone)
