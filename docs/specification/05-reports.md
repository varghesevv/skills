# 05 Reports

Decision record: [ADR-0006](../adr/0006-scheduled-reports-in-a-worker-process.md).

## Who sees reports

Reports are for the OWNER (all churches) and each church's ADMIN (their church only; the server always limits an ADMIN's data to their church). VERIFIERs, providers and searchers see no reports; a VERIFIER has the verifier screens instead. Reports hold **counts and aggregates only**: no name, email or mobile number appears in a report or its files.

## Standard reports (UI pages and API)

| ID | Report | Filters | Audience |
|---|---|---|---|
| RP-01 | Sign-ups per day by requested status and by church | date range, church | OWNER, ADMIN (own church) |
| RP-02 | Active people (by last login) and login success/failure counts | date range, status | OWNER |
| RP-03 | Providers by skill, language, nativity, timing | church | OWNER, ADMIN (own church) |
| RP-04 | Top-rated providers and average rating per skill | date range, min ratings | OWNER |
| RP-05 | Verification summary: per church and home group, people by status (pending, searchers, providers, verifiers, revoked), admissions and declines in the period, average days from sign-up to admission, vouches per admission | date range, church | OWNER, ADMIN (own church) |
| RP-06 | Rate distribution by skill (average, min, max per currency) | skill, currency | OWNER |
| RP-07 | Provider availability overview | date range | OWNER, ADMIN (own church) |
| RP-08 | Mobile number reveals: summary (reveals, searchers, phone vs computer, search vs detail page, share of searcher and provider pairs rated afterwards), per day, per searcher, per skill of the provider, skills searched before a reveal, most revealed providers | date range | OWNER |
| RP-09 | Trust events: revocations, reinstatements, re-check flags raised and cleared, leader changes, group and church closures, moves | date range, church | OWNER, ADMIN (own church) |

Every report supports on-screen table, chart where useful, and CSV download.

## Scheduled reports

| Report | Default schedule | Content |
|---|---|---|
| **Sign-ups in the last day** | daily 00:05 | New applicants in the previous day by requested status and church, with counts |
| Weekly summary | Monday 06:00 | RP-05 and RP-09 |
| Monthly summary | 1st of month 06:00 | RP-01 to RP-09 |

Rules:

- Time zone configurable; default Asia/Dubai (Q8). The window is computed in that zone and stored in UTC.
- Output as CSV and HTML in a configured output directory; each run recorded in `report_runs` (status, file, row count, error).
- Idempotent: the same report and window never creates duplicate runs; a failed run retries once.
- Optional email delivery to configured recipients through SMTP.
- Schedules are stored in `report_schedules` and editable by the OWNER; defaults seeded by migration.
- CLI: `python -m app.reports run <name> --from <date> --to <date>`.
- Exactly one worker runs schedules (or a PostgreSQL advisory lock guards runs).

## Implementation notes (phase 6)

- Report names (used in URLs, the CLI and `report_schedules`): `registrations_per_day` (RP-01), `active_users` (RP-02), `providers_by_label` (RP-03), `top_rated` (RP-04), `verification_summary` (RP-05, replaces `vouching_summary`), `rate_distribution` (RP-06), `availability_overview` (RP-07, at most 93 days), `phone_reveals` (RP-08), `trust_events` (RP-09), and the scheduled `signups_daily` (replaces `users_registered_daily`), `weekly_summary` (RP-05 and RP-09) and `monthly_summary` (RP-01 to RP-09). The report code is redone in slice S5.3; until then the code keeps the older names.
- A report returns one or more **sections** (title, columns, rows). `row_count` in the run history is the total number of rows over all sections.
- Windows are whole days in the report time zone, `[start, end)` stored in UTC. Scheduled windows: yesterday (daily), the previous Monday to Sunday (weekly), the previous calendar month (monthly). On-demand dates (`from`, `to`) include both days; the default is the last 30 days.
- Files go to `REPORTS_OUTPUT_DIR` as `<report>/<start>_<end>.csv` and `.html` (in docker compose: the `reports_data` volume at `/data/reports`). CSV cells that start with `=`, `+`, `-` or `@` are prefixed with `'` so spreadsheets do not run them as formulas.
- Idempotency: one `report_runs` row per report and window. A succeeded run is never repeated; a failed run, or a run stuck in `running` for more than an hour, is executed again. A failed scheduled run is retried once after 30 seconds.
- The worker reads `report_schedules` at start and then every minute, so the OWNER can change a schedule (`PUT /reports/schedules/{report}`) without restarting it. After a restart it also runs any window that was missed while it was down.
- Not built yet: email delivery of reports (open question Q7, needs SMTP settings and a secret).
- Run exactly one worker. Two workers cannot create duplicate runs (a unique constraint guards each window), but they would repeat the work.
