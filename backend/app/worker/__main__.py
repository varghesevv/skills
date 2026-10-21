"""Scheduled report worker (ADR-0006). Report jobs are registered in phase 6."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("skills.worker")


def main() -> None:
    scheduler = BlockingScheduler()
    log.info("Worker started; no report jobs registered yet")
    scheduler.start()


if __name__ == "__main__":
    main()
