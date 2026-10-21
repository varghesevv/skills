"""Scheduled report worker (ADR-0006). Report jobs are registered in phase 6."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import get_settings
from app.core.logging_config import configure_logging

log = logging.getLogger("skills.worker")


def main() -> None:
    configure_logging()
    get_settings()  # fails fast when a secret is missing or too weak
    scheduler = BlockingScheduler()
    log.info("Worker started; no report jobs registered yet")
    scheduler.start()


if __name__ == "__main__":
    main()
