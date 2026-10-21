# ADR-0006: Scheduled reports in a separate worker process

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

Reports such as "users registered in the last day" must be generated on a schedule, independent of web requests.

## Decision

Run a separate **worker** process (APScheduler) from the same codebase. Each report is a registered function; each run is recorded in a `report_runs` table with output files. Reports are also runnable manually through a CLI.

## Alternatives considered

- Scheduler inside the API process: duplicates runs when the API is scaled to several instances.
- Celery + Redis: more infrastructure than needed now.
- OS cron only: harder to see history and configure from the app.

## Consequences

- API can scale independently from the scheduler.
- Run exactly one worker instance, or add a PostgreSQL advisory lock so two workers never run the same report.
- Reruns are idempotent per report and time window.
