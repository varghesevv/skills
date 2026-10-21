from datetime import UTC, date, datetime

import pytest

from app.reports.types import ReportError
from app.reports.windows import default_window, scheduled_window, window_from_dates

DUBAI = "Asia/Dubai"  # UTC+4, no daylight saving


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_dates_are_whole_days_in_the_report_time_zone() -> None:
    start, end = window_from_dates(date(2026, 10, 20), date(2026, 10, 21), DUBAI)
    assert start == utc(2026, 10, 19, 20)  # 00:00 in Dubai
    assert end == utc(2026, 10, 21, 20)  # the end of the 21st


def test_invalid_windows_are_rejected() -> None:
    with pytest.raises(ReportError):
        window_from_dates(date(2026, 10, 21), date(2026, 10, 20), DUBAI)
    with pytest.raises(ReportError):
        window_from_dates(date(2025, 1, 1), date(2026, 12, 31), DUBAI)
    with pytest.raises(ReportError):
        window_from_dates(date(2026, 10, 1), date(2026, 10, 2), "Not/AZone")


def test_daily_window_is_yesterday_in_dubai() -> None:
    # 00:05 in Dubai on 22 October is 20:05 UTC on the 21st.
    start, end = scheduled_window("users_registered_daily", utc(2026, 10, 21, 20, 5), DUBAI)
    assert start == utc(2026, 10, 20, 20)
    assert end == utc(2026, 10, 21, 20)


def test_weekly_window_is_the_previous_monday_to_sunday() -> None:
    # Monday 26 October 2026, 06:00 in Dubai.
    start, end = scheduled_window("weekly_summary", utc(2026, 10, 26, 2), DUBAI)
    assert start == utc(2026, 10, 18, 20)  # Monday 19 October 00:00 Dubai
    assert end == utc(2026, 10, 25, 20)  # Monday 26 October 00:00 Dubai


def test_monthly_window_is_the_previous_calendar_month() -> None:
    start, end = scheduled_window("monthly_summary", utc(2026, 11, 1, 2), DUBAI)
    assert start == utc(2026, 9, 30, 20)  # 1 October 00:00 Dubai
    assert end == utc(2026, 10, 31, 20)  # 1 November 00:00 Dubai
    december, _ = scheduled_window("monthly_summary", utc(2027, 1, 1, 2), DUBAI)
    assert december == utc(2026, 11, 30, 20)  # December starts 1 Dec 00:00 Dubai


def test_default_window_is_the_last_complete_days() -> None:
    start, end = default_window(utc(2026, 10, 22, 10), DUBAI, days=30)
    assert end == utc(2026, 10, 21, 20)
    assert (end - start).days == 30
