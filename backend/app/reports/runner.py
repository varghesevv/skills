"""Run a report for a window, write its files and record the run (idempotent)."""

import logging
import os
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging_config import redact
from app.models.reports import ReportRun
from app.reports.definitions import get_definition
from app.reports.render import to_csv, to_html
from app.reports.types import ReportParams, ReportResult

log = logging.getLogger("skills.reports")

STALE_RUN = timedelta(hours=1)  # a "running" row older than this is treated as abandoned
SessionFactory = Callable[[], AbstractContextManager[Session]]


def build_report(db: Session, name: str, params: ReportParams) -> ReportResult:
    return ReportResult(get_definition(name).build(db, params))


def output_paths(output_dir: Path, name: str, start: datetime, end: datetime) -> tuple[Path, Path]:
    stem = f"{start:%Y%m%dT%H%M}_{end:%Y%m%dT%H%M}"
    folder = output_dir / name
    return folder / f"{stem}.csv", folder / f"{stem}.html"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def run_report(
    db: Session, name: str, start: datetime, end: datetime, *, output_dir: Path, timezone: str
) -> tuple[ReportRun, bool]:
    """Run once per report and window. Returns (run, executed).

    A succeeded run is returned as it is; a failed or abandoned run is executed again.
    """
    definition = get_definition(name)
    now = datetime.now(UTC)
    where = (
        ReportRun.report_name == name,
        ReportRun.window_from == start,
        ReportRun.window_to == end,
    )
    run = db.scalar(select(ReportRun).where(*where).with_for_update())
    if run is None:
        run = ReportRun(report_name=name, window_from=start, window_to=end, started_at=now)
        db.add(run)
        try:
            db.commit()
        except IntegrityError:  # another process created it first
            db.rollback()
            existing = db.scalar(select(ReportRun).where(*where))
            assert existing is not None  # noqa: S101
            return existing, False
    elif run.status == "succeeded" or (
        run.status == "running" and now - run.started_at < STALE_RUN
    ):
        return run, False
    else:
        run.status, run.started_at, run.error_message, run.finished_at = "running", now, None, None
        db.commit()

    run_id = run.id
    try:
        result = build_report(db, name, ReportParams(start=start, end=end, timezone=timezone))
        csv_path, html_path = output_paths(output_dir, name, start, end)
        _write(csv_path, to_csv(result))
        _write(html_path, to_html(definition.title, start, end, result))
        run = db.get_one(ReportRun, run_id)
        run.status = "succeeded"
        run.file_path = str(csv_path.relative_to(output_dir))
        run.row_count = result.row_count
    except Exception as exc:  # noqa: BLE001 - any failure is recorded, then reported
        db.rollback()
        log.exception("Report %s failed", name)
        run = db.get_one(ReportRun, run_id)
        run.status = "failed"
        run.error_message = redact(f"{type(exc).__name__}: {exc}")[:500]
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run, True


def run_with_retry(
    factory: SessionFactory,
    name: str,
    start: datetime,
    end: datetime,
    *,
    output_dir: Path,
    timezone: str,
    wait_seconds: float = 30.0,
) -> str:
    """Run a report; if it fails, wait and try once more. Returns the final status."""
    status = "failed"
    for attempt in (1, 2):
        with factory() as db:
            run, _ = run_report(db, name, start, end, output_dir=output_dir, timezone=timezone)
            status = run.status
        if status != "failed":
            break
        if attempt == 1:
            log.warning("Report %s failed; retrying once in %s seconds", name, wait_seconds)
            time.sleep(wait_seconds)
    return status
