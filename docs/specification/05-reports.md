# 05 Reports

Decision record: [ADR-0006](../adr/0006-scheduled-reports-in-a-worker-process.md).

## Standard reports (UI pages and API)

| ID | Report | Filters | Audience |
|---|---|---|---|
| RP-01 | Registrations per day by user type | date range | admin |
| RP-02 | Active users (by last login) and login success/failure counts | date range, user type | admin |
| RP-03 | Freelancers by skill, language, nativity, timing | none | admin |
| RP-04 | Top-rated freelancers and average rating per skill | date range, min ratings | admin |
| RP-05 | Organisation vouching summary (freelancers per organisation, active vs inactive) | org | admin, organisation (own) |
| RP-06 | Rate distribution by skill (average, min, max per currency) | skill, currency | admin |
| RP-07 | Freelancer availability overview | date range | admin |

Every report supports on-screen table, chart where useful, and CSV download.

## Scheduled reports

| Report | Default schedule | Content |
|---|---|---|
| **Users registered in the last day** | daily 00:05 | New freelancers, work hosts, organisations in the previous day, with counts and rows |
| Weekly summary | Monday 06:00 | RP-04 and RP-05 |
| Monthly summary | 1st of month 06:00 | RP-01 to RP-07 |

Rules:

- Time zone configurable; default Asia/Dubai (Q8). The window is computed in that zone and stored in UTC.
- Output as CSV and HTML in a configured output directory; each run recorded in `report_runs` (status, file, row count, error).
- Idempotent: the same report and window never creates duplicate runs; a failed run retries once.
- Optional email delivery to configured recipients through SMTP.
- Schedules are stored in `report_schedules` and editable by admin; defaults seeded by migration.
- CLI: `python -m app.reports run <name> --from <date> --to <date>`.
- Exactly one worker runs schedules (or a PostgreSQL advisory lock guards runs).
