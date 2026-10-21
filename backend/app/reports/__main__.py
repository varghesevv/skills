"""Command line: run a report for a date range, or list the reports.

    python -m app.reports list
    python -m app.reports run users_registered_daily --from 2026-10-20 --to 2026-10-20

Dates are whole days in the report time zone, both included. Running the same report and
window again does nothing if the earlier run succeeded.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging_config import configure_logging
from app.reports.definitions import REPORTS, get_definition
from app.reports.runner import run_report
from app.reports.types import ReportError
from app.reports.windows import window_from_dates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.reports")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list the available reports")
    run = sub.add_parser("run", help="run a report for a date range")
    run.add_argument("name")
    run.add_argument("--from", dest="first", type=date.fromisoformat, required=True)
    run.add_argument("--to", dest="last", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    configure_logging()

    if args.command == "list":
        for report in REPORTS:
            print(f"{report.name:<26} {report.code}  {report.title}")
        return 0

    settings = get_settings()
    try:
        get_definition(args.name)
        start, end = window_from_dates(args.first, args.last, settings.report_timezone)
    except ReportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        result, executed = run_report(
            db,
            args.name,
            start,
            end,
            output_dir=Path(settings.reports_output_dir),
            timezone=settings.report_timezone,
        )
        status, file_path, rows = result.status, result.file_path, result.row_count
    if status == "failed":
        print("The report failed; see the run history for details.", file=sys.stderr)
        return 1
    note = "" if executed else " (already done earlier, nothing changed)"
    print(f"{args.name}: {status}, {rows} rows, file {file_path}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
