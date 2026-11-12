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

## Open details, to be settled in the named pull request

| # | Detail | Default until settled | Settled in |
|---|---|---|---|
| O-01 | Lifetime and entropy of a vouch link and of a group invitation link; rate limits for them | Long random token stored hashed, expiry, rate limits, nothing revealed about whether a link exists (roadmap section 5) | S1.4, S3.1 |
| O-02 | Which events create an in-app notification, and how long they are kept | The events the model names | S1.4, S3.3 |
| O-03 | Retention of the log of verifier views of phone numbers | Kept with the trust record | S1.4, S3.2 |
| O-04 | The terminology keys for searcher, provider, verifier, admin, owner, church and home group | One key each, backend and web copies kept equal | S2.9 |
| O-05 | Fate of each old table (organisations, vouches, admin accounts) | Removed by the destructive migration | S1.2, S2.1 |
| O-06 | Whether the list of churches, home groups and leader names is public (needed before an account exists) or shown only after the first sign-up step, and how it is rate limited against scraping | Shown inside the sign-up flow and to PENDING applicants, names only, rate limited | S1.3, S1.4 |
| O-07 | Retention of login history rows with no person (failed attempts) and of expired admin invitations | Keep login history 12 months, delete expired invitations after 30 days | S1.4 |
