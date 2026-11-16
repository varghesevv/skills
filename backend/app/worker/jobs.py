"""Scheduled report jobs, driven by the report_schedules table."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.chat.push import PushSender, process_due, purge_finished
from app.chat.retention import delete_orphaned_conversations
from app.core.config import Settings
from app.models.reports import ReportSchedule
from app.reports.definitions import REGISTRY
from app.reports.runner import SessionFactory, run_with_retry
from app.reports.windows import scheduled_window, zone_of

log = logging.getLogger("skills.worker")

SYNC_JOB_ID = "__sync_schedules__"
PUSH_JOB_ID = "__chat_push__"
PURGE_JOB_ID = "__chat_push_purge__"


def push_due(factory: SessionFactory, sender: PushSender) -> None:
    """Send the chat pushes that are due (a failure is logged; the next run tries again)."""
    try:
        process_due(factory, sender)
    except Exception:  # noqa: BLE001 - one bad run must not stop the worker
        log.exception("Chat push run failed")


def purge_push(factory: SessionFactory, settings: Settings) -> None:
    """The hourly clean-up of chat: finished push rows, and conversations nobody can read any
    more (both accounts closed, which a closing cannot always see when two happen at once)."""
    try:
        with factory() as db:
            deleted = purge_finished(db, settings)
            orphaned = delete_orphaned_conversations(db)
            db.commit()
        if deleted:
            log.info("Deleted %d finished push rows", deleted)
        if orphaned:
            log.info("Deleted %d conversations with no one left", orphaned)
    except Exception:  # noqa: BLE001
        log.exception("Cleaning up chat failed")


def run_scheduled_report(
    factory: SessionFactory, settings: Settings, report_name: str, timezone: str
) -> None:
    """Run the latest complete window of a report (a no-op if it was already done)."""
    start, end = scheduled_window(report_name, datetime.now(UTC), timezone)
    status = run_with_retry(
        factory,
        report_name,
        start,
        end,
        output_dir=Path(settings.reports_output_dir),
        timezone=timezone,
    )
    log.info("Scheduled report %s for %s to %s: %s", report_name, start, end, status)


def _signature(schedule: ReportSchedule) -> str:
    return f"{schedule.cron_expression}|{schedule.timezone}"


def sync_jobs(scheduler: BaseScheduler, factory: SessionFactory, settings: Settings) -> list[str]:
    """Make the scheduler's jobs match the enabled schedules. Returns the report names."""
    with factory() as db:
        schedules = list(
            db.scalars(select(ReportSchedule).where(ReportSchedule.is_enabled.is_(True)))
        )
    wanted: dict[str, ReportSchedule] = {}
    for schedule in schedules:
        if schedule.report_name not in REGISTRY:
            log.warning("Schedule for unknown report %s ignored", schedule.report_name)
            continue
        wanted[schedule.report_name] = schedule

    for job in scheduler.get_jobs():
        if job.id != SYNC_JOB_ID and job.id not in wanted:
            job.remove()
    for name, schedule in wanted.items():
        existing = scheduler.get_job(name)
        if existing is not None and existing.name == _signature(schedule):
            continue
        try:
            trigger = CronTrigger.from_crontab(
                schedule.cron_expression, timezone=zone_of(schedule.timezone)
            )
        except ValueError:
            log.error("Schedule for %s has an invalid cron expression or time zone", name)
            continue
        scheduler.add_job(
            run_scheduled_report,
            trigger,
            args=[factory, settings, name, schedule.timezone],
            id=name,
            name=_signature(schedule),
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
        log.info("Scheduled %s: %s (%s)", name, schedule.cron_expression, schedule.timezone)
    return sorted(wanted)


def catch_up(factory: SessionFactory, settings: Settings) -> None:
    """After a restart, run any window that was missed while the worker was down."""
    with factory() as db:
        schedules = list(
            db.scalars(select(ReportSchedule).where(ReportSchedule.is_enabled.is_(True)))
        )
    for schedule in schedules:
        if schedule.report_name in REGISTRY:
            try:
                run_scheduled_report(factory, settings, schedule.report_name, schedule.timezone)
            except Exception:  # noqa: BLE001 - one report must not stop the worker
                log.exception("Catch-up run of %s failed", schedule.report_name)
