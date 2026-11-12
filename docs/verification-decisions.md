# Verification model: decision log

Where every choice that the [verification rules](verification.md) leave open is recorded, so it is decided once and found again. The rules themselves change only in a pull request that says it is a model change. This log never overrides them.

Add a row in the same pull request that makes the decision. Columns: the number, the date, the decision, why, and the pull request that made it. Status is **decided**, or **open** with the default in force until a pull request settles it.

## Decisions

| # | Date | Decision | Why | Pull request | Status |
|---|---|---|---|---|---|
| D-01 | 2026-11-12 | ADR-0016 (the church trust model) is accepted. ADR-0017 (authorisation by status) replaces ADR-0004. | The model is the basis of all new work. | #101 | decided |
| D-02 | 2026-11-12 | Work is split between `main` (demo-safe changes only) and the integration branch `model/verification`, merged into `main` once, at the cut-over. | Every merge to `main` deploys the demo. | #101 | decided |
| D-03 | 2026-11-12 | The demo data may be wiped and reseeded; there are no real users. | Lets the migration be destructive. | #101 | decided |
| D-04 | 2026-11-12 | `/api/v1` is changed in place; nothing was released outside internal testing. Resource paths for providers and searchers stay. | No external clients to keep compatible. | #101 | decided |
| D-05 | 2026-11-12 | The platform admin becomes the OWNER. The OWNER manages labels. | One person at the top of the structure. | #101 | decided |
| D-06 | 2026-11-12 | A person has one account and one status. Work host becomes SEARCHER, freelancer becomes PROVIDER, organisation becomes the church (a structure, not an account). | Matches the model's ladder. | #101 | decided |
| D-07 | 2026-11-12 | Verifiers see the phone numbers of people in their scope on their own screens only, and each view is logged. Search results never show a number. This is a second path next to the reveal endpoint: the rule that only the reveal endpoint returns a number (searchers only, recorded, rate limited) stays for search and detail, and the specification is changed to name the verifier views as the one exception (S1.4). | Verifiers must know their people; the number stays out of discovery. | #101 | decided |
| D-08 | 2026-11-12 | Pictures are deferred; the app and web show an initials avatar. | Keeps the first version small. | #101 | decided |
| D-09 | 2026-11-12 | Notifications are in-app first. Email is added when a mail service is chosen; push comes with chat. | No mail service chosen yet. | #101 | decided |
| D-10 | 2026-11-12 | Chat: any admitted person (SEARCHER or above) may start a conversation with a provider they found. The provider can reply, mute, block and report. | Replaces the older "work host starts" rule. | #102 | decided |
| D-11 | 2026-11-12 | OWNER actions are on the web only. ADMIN and VERIFIER actions are in the app and on the web. | The OWNER's tasks are rare and administrative. | #101 | decided |
| D-12 | 2026-11-12 | Closing an account keeps the person's row with `closedAt` set, clears the personal fields (name, email, phone, picture), and keeps the status history with the ids of who changed what. Nothing is ever hard-deleted. The same flow is the in-app "delete account" the stores require. | The chain of trust must stay readable. | #101 | decided |
| D-13 | 2026-11-12 | Merge policy: a pull request is merged when every required check is green and the review comments are handled. Pull requests that touch `.github/` or `infra/` wait for the owner. The demo is deployed only at the cut-over, with the owner's go-ahead. | See [CONTRIBUTING](../CONTRIBUTING.md). | #102 | decided |
| D-14 | 2026-11-12 | The planning answers were not given in writing, so the defaults of the [roadmap](roadmap-verification-model.md) section 8 are in force until the owner corrects them. | Work must not wait. | #102 | decided |
| D-15 | 2026-11-12 | A revoked person can still log in with the correct password but every endpoint except their own status, token refresh, logout, password reset and app config answers `account_revoked`; a pending applicant reaches only their own application, the list of churches and groups, and notifications. A person out of a verifier's scope is reported as not found. | Lets people see why they have no access, without revealing who exists. | S1.3 | decided |
| D-16 | 2026-11-12 | Link and invitation tokens: at least 128 bits, stored hashed, vouch and group links expire after 30 days, admin invitations after 14, identical `404` for every failure. Limits as in specification 07. | Settles O-01. | S1.4 | decided |
| D-17 | 2026-11-12 | A verifier sees a mobile number only in `GET /verifier/people/{id}`, one person at a time, within scope; lists never carry numbers; each call is logged without the number and the log is readable by the OWNER only. | Settles the detail of D-07. | S1.4 | decided |
| D-18 | 2026-11-12 | Notifications are rows written in the same transaction as their event; clients poll every 60 seconds while open. | Settles the delivery part of O-02; which events notify and the retention stay open. | S1.4 | decided |
| D-19 | 2026-11-12 | The list of churches, home groups and leader names is public, names only, rate limited at 60 requests per minute per IP. Hiding leader names from anonymous callers is not done: choosing a group needs them. | Settles O-06. | S1.4 | decided |
| D-20 | 2026-11-13 | The new identity schema is added next to the old one (migration 0007) instead of replacing it at once. Each old table is dropped when its feature moves to the new identity; the old identity tables go last. | Keeps the backend and its tests working and CI green while the work is spread over many pull requests. The demo is still wiped at the cut-over (D-03). | S2.1 | decided |
| D-21 | 2026-11-13 | The owner confirmed the defaults of section 8 of the roadmap (D-14) and asked to proceed with S2. | | S2 | decided |

## Open details, to be settled in the named pull request

| # | Detail | Default until settled | Settled in |
|---|---|---|---|
| O-02 | Which events create an in-app notification, and how long they are kept | The events the model names; kept 12 months | S3.3 |
| O-03 | Retention of the log of verifier views of phone numbers | Kept 12 months | S3.2 |
| O-04 | The terminology keys for searcher, provider, verifier, admin, owner, church and home group | One key each, backend and web copies kept equal | S2.9 |
| O-07 | Retention of login history rows with no person (failed attempts) and of expired admin invitations | Keep login history 12 months, delete expired invitations after 30 days | S2.3 |
