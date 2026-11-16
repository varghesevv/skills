# 05 Reports

Decision record: [ADR-0006](../adr/0006-scheduled-reports-in-a-worker-process.md).

## Who sees reports

Reports are for the OWNER (all churches) and each church's ADMIN (their church only; the server always limits an ADMIN's data to their church). VERIFIERs, providers and searchers see no reports; a VERIFIER has the verifier screens instead. Reports hold **aggregates**: no name, email or mobile number appears in a report or its files. The few rows that are about one person (RP-04 top-rated providers, and RP-08 per searcher and most revealed providers) show a short reference code (the first 8 characters of the person's id) instead of a name, and those reports are OWNER only.

## Standard reports (UI pages and API)

| ID | Report | Filters | Audience |
|---|---|---|---|
| RP-01 | Sign-ups per day by church and by status now | date range, church | OWNER, ADMIN (own church) |
| RP-02 | Active people (by last login) and login success/failure counts | date range, status | OWNER |
| RP-03 | Providers by skill, language, nativity, timing | church | OWNER, ADMIN (own church) |
| RP-04 | Top-rated providers and average rating per skill | date range, min ratings | OWNER |
| RP-05 | Verification summary: per church and home group, people by status (pending, searchers, providers, verifiers, revoked), admissions and declines in the period, average days from sign-up to admission, vouches per admission | date range, church | OWNER, ADMIN (own church) |
| RP-06 | Rate distribution by skill (average, min, max per currency) | skill, currency | OWNER |
| RP-07 | Provider availability overview | date range | OWNER, ADMIN (own church) |
| RP-08 | Mobile number reveals: summary (reveals, searchers, phone vs computer, search vs detail page, share of searcher and provider pairs rated afterwards), per day, per searcher, per skill of the provider, skills searched before a reveal, most revealed providers | date range | OWNER |
| RP-09 | Trust events: revocations, reinstatements, re-check flags raised and cleared, leader changes, group and church closures, moves | date range, church | OWNER, ADMIN (own church) |
| RP-10 | Chat reports (S8.4): reports of a conversation in the period, by reason (reports, handled, open) and by week. Counts only; no names, no message text, no notes | date range | OWNER |
| RP-11 | Chat metrics (S8.10): conversations started, messages and people who wrote, how often the first message of a conversation is answered and the median minutes to the first answer, and how many of the numbers revealed in the period lead to a conversation within 7 days (a conversation between the same two people, whoever wrote first). Counts only; no names, text or ids | date range | OWNER |

Every report supports on-screen table, chart where useful, and CSV download.

## Scheduled reports

| Report | Default schedule | Content |
|---|---|---|
| **Sign-ups in the last day** | daily 00:05 | New applicants in the previous day by requested status and church, with counts |
| Weekly summary | Monday 06:00 | RP-05 and RP-09 |
| Monthly summary | 1st of month 06:00 | RP-01 to RP-09 |

Rules:

- **Scheduled runs, run history, kept files and e-mailed reports are OWNER only and cover the whole platform.** An ADMIN gets reports on demand only, limited to their church, and never sees `report_runs`, schedules or files. Recipients of e-mailed reports are set by the OWNER.

- Time zone configurable; default Asia/Dubai (Q8). The window is computed in that zone and stored in UTC.
- Output as CSV and HTML in a configured output directory; each run recorded in `report_runs` (status, file, row count, error).
- Idempotent: the same report and window never creates duplicate runs; a failed run retries once.
- Optional email delivery to configured recipients through SMTP.
- Schedules are stored in `report_schedules` and editable by the OWNER; defaults seeded by migration.
- CLI: `python -m app.reports run <name> --from <date> --to <date>`.
- Exactly one worker runs schedules (or a PostgreSQL advisory lock guards runs).

## Implementation notes (phase 6)

- Report names (used in URLs, the CLI and `report_schedules`): `registrations_per_day` (RP-01), `active_users` (RP-02), `providers_by_label` (RP-03), `top_rated` (RP-04), `verification_summary` (RP-05, replaces `vouching_summary`), `rate_distribution` (RP-06), `availability_overview` (RP-07, at most 93 days), `phone_reveals` (RP-08), `trust_events` (RP-09), `chat_reports` (RP-10, OWNER only), `chat_metrics` (RP-11, OWNER only), and the scheduled `signups_daily` (replaces `users_registered_daily`), `weekly_summary` (RP-05 and RP-09) and `monthly_summary` (RP-01 to RP-09). The report code was redone on people in slice S5.3a (D-44): the schedule `users_registered_daily` is renamed `signups_daily` by migration 0017, and the CLI and the operations runbook use the new names. Old `report_runs` rows and files are dropped with the rest of the older data at the cut-over (the demo data is wiped, D-03). The rule that names do not change applies to wording changes (terminology), not to a change of model. Who may run what: the OWNER runs every report, for every church or one (`church_id`); an ADMIN runs only those marked for them in the table above, and always for their own church (`church_id` is ignored for an ADMIN); `403 forbidden` otherwise, and `403 not_admitted` below ADMIN. The OWNER alone has run history, kept files, downloads and schedules. Filters: `status` (RP-02), `church_id`, `skill` and `currency` (RP-06), `min_ratings` (RP-04).
- What a report can say, and what it cannot (D-44): RP-01 and the daily sign-ups count people by church and, for RP-01, by the status they have now, because the status a person asked for is not kept once they are decided; the daily report uses the requested status while it is still set. RP-09 counts the re-checks done (flags cleared by a re-confirmation) in the period and the people flagged now, because the raising of a flag is not an event of its own. RP-05 counts a decline as an applicant whose account was closed in the period while pending (a leader's decline closes it, D-27; an applicant who closed it themselves is counted too).
- A report returns one or more **sections** (title, columns, rows). `row_count` in the run history is the total number of rows over all sections.
- Windows are whole days in the report time zone, `[start, end)` stored in UTC. Scheduled windows: yesterday (daily), the previous Monday to Sunday (weekly), the previous calendar month (monthly). On-demand dates (`from`, `to`) include both days; the default is the last 30 days.
- Files go to `REPORTS_OUTPUT_DIR` as `<report>/<start>_<end>.csv` and `.html` (in docker compose: the `reports_data` volume at `/data/reports`). CSV cells that start with `=`, `+`, `-` or `@` are prefixed with `'` so spreadsheets do not run them as formulas.
- Idempotency: one `report_runs` row per report and window. A succeeded run is never repeated; a failed run, or a run stuck in `running` for more than an hour, is executed again. A failed scheduled run is retried once after 30 seconds.
- The worker reads `report_schedules` at start and then every minute, so the OWNER can change a schedule (`PUT /reports/schedules/{report}`) without restarting it. After a restart it also runs any window that was missed while it was down.
- Not built yet: email delivery of reports (open question Q7, needs SMTP settings and a secret).
- Run exactly one worker. Two workers cannot create duplicate runs (a unique constraint guards each window), but they would repeat the work.
