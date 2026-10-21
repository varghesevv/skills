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

## Implementation notes (phase 6)

- Report names (used in URLs, the CLI and `report_schedules`): `registrations_per_day` (RP-01), `active_users` (RP-02), `freelancers_by_label` (RP-03), `top_rated` (RP-04), `vouching_summary` (RP-05), `rate_distribution` (RP-06), `availability_overview` (RP-07, at most 93 days), and the scheduled `users_registered_daily`, `weekly_summary` (RP-04 and RP-05) and `monthly_summary` (RP-01 to RP-07).
- A report returns one or more **sections** (title, columns, rows). `row_count` in the run history is the total number of rows over all sections.
- Windows are whole days in the report time zone, `[start, end)` stored in UTC. Scheduled windows: yesterday (daily), the previous Monday to Sunday (weekly), the previous calendar month (monthly). On-demand dates (`from`, `to`) include both days; the default is the last 30 days.
- Files go to `REPORTS_OUTPUT_DIR` as `<report>/<start>_<end>.csv` and `.html` (in docker compose: the `reports_data` volume at `/data/reports`). CSV cells that start with `=`, `+`, `-` or `@` are prefixed with `'` so spreadsheets do not run them as formulas.
- Idempotency: one `report_runs` row per report and window. A succeeded run is never repeated; a failed run, or a run stuck in `running` for more than an hour, is executed again. A failed scheduled run is retried once after 30 seconds.
- The worker reads `report_schedules` at start and then every minute, so an admin can change a schedule (`PUT /reports/schedules/{report}`) without restarting it. After a restart it also runs any window that was missed while it was down.
- Not built yet: email delivery of reports (open question Q7, needs SMTP settings and a secret).
- Run exactly one worker. Two workers cannot create duplicate runs (a unique constraint guards each window), but they would repeat the work.
