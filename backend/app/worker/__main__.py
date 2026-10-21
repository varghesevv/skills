"""Scheduled report worker (ADR-0006). Run exactly one instance."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging_config import configure_logging
from app.worker.jobs import SYNC_JOB_ID, catch_up, sync_jobs

log = logging.getLogger("skills.worker")


def main() -> None:
    configure_logging()
    settings = get_settings()  # fails fast when a secret is missing or too weak
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    scheduler = BlockingScheduler(timezone="UTC")

    names = sync_jobs(scheduler, factory, settings)
    log.info("Worker started with %d scheduled report(s): %s", len(names), ", ".join(names))
    catch_up(factory, settings)
    # Pick up schedule changes made by an admin without restarting the worker.
    scheduler.add_job(
        sync_jobs,
        IntervalTrigger(seconds=60),
        args=[scheduler, factory, settings],
        id=SYNC_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
