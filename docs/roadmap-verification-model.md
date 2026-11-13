# Roadmap: moving Skills to the church trust model

Status: plan, version 2, 2026-11-12. Rules being built: [verification rules](verification.md) ([ADR-0016](adr/0016-church-trust-hierarchy-verification-model.md), accepted). Authorisation: [ADR-0017](adr/0017-authorisation-by-status.md). This file is the source of truth for progress: each pull request ticks its own line and updates the state block.

## 0. State (update in every pull request)

- Done: S0.1 (pull request 101), S0.2 (102), S0.3 (103); mobile ratings (100).
- Done also: S0.4 (104), S1.1 (105), S1.2 (106), S1.3 (107), S1.4 (108), S1.5 (109); S1 (specification) is complete. The owner confirmed the defaults of section 8 on 2026-11-13 and asked to proceed with S2.
- Done also: S2.1 (110), S2.2 (111), S2.3 (112), S2.4 (113), S2.5 (114), S2.6 (115), S2.7 (116, 117), S2.8 (118), S2.9 (119); S2 (identity and sign-up) is complete.
- Done also: S3.1 (120), S3.2 (122), S3.3 (123), S3.4 (124), S3.5a (125), S3.6 (128).
- In progress: nothing.
- Next: S3.5 (web: verifier screens).
- Waiting on the owner: see section 7. The owner confirmed the defaults of section 8 on 2026-11-13 (decision D-21) and allowed merging with the administrator override while the review rule stays in place.
## 1. Why this shape (changes from the first draft)

The first draft built all of the backend, then the web, then the mobile app. That proves nothing end to end until about the 35th pull request, so a wrong design choice would show up late and cost a lot. It is replaced by **vertical slices**: each slice delivers one capability on the backend, the web and the mobile app, with tests, and ends with a flow that can be shown. Also added after review:

- Safety of the cut-over: backup, rollback, forcing old app builds to update, old sessions, version bump.
- Tests that protect the model itself: one test per invariant, a table-driven permission matrix (every actor status against every target status and operation), and a seeded random-sequence test that applies many operations and checks the invariants after each.
- Abuse protection for vouch and invitation links, privacy of the verifier screens, search performance at the expected size, operator procedures, and a decision log.
- Explicit dependencies, and a verified way to run the database tests locally (section 6).

## 2. How the work is organised

- **Two lines.**
  - `main` is deployed to the demo server after every successful image build. It only receives changes that cannot break the running demo (documents, tooling, the release pipeline, the web Downloads page).
  - `model/verification` is a long-lived integration branch. Every change that depends on the new model is a small pull request into it, merged as soon as checks pass. `main` is merged into it regularly, so it does not drift. One cut-over pull request (S6) merges the finished branch into `main`, so the demo is switched exactly once.
- **Pull request rules.** One topic. Tests with the code. Specification, parity table and runbook updated in the same pull request. A conventional title. Titles, commit messages, descriptions and review replies describe the change and nothing else (no tool names, no generated-by lines).
- **Order inside a slice.** Backend, then web, then mobile. Each is merged before the next starts.

## 3. The loop for each pull request

1. Branch from the right base (`main` or `model/verification`).
2. Implement with tests. Run everything that exists for the area: backend `ruff`, `ruff format --check`, `mypy`, `pytest` against a local PostgreSQL, OpenAPI export check; web lint, format check, typecheck, tests, build; mobile `dart format`, `flutter analyze`, tests with coverage, the contract test; secret scan, link check, fork-guard check.
3. Update the matching specification file, parity table, runbook and this roadmap.
4. Push, open the pull request, wait for the required checks.
5. Read the automated review comments. Fix the valid ones. Answer the invalid ones with evidence. Resolve the threads.
6. Squash-merge when every required check is green; delete the branch.
7. Stop and report (instead of continuing) when:
   - a check still fails after three honest attempts;
   - the change needs a secret or a value only the owner has;
   - the pull request touches `.github/` or `infra/` (owner approval is required);
   - the change would contradict the verification model (the model is only changed in a pull request that says so);
   - anything would touch the live demo server or real data.

## 4. Slices

Counts are targets; a pull request may split.

### S0. Foundations (on `main`) — 4 pull requests
- [x] 0.1 Decision records and this roadmap: ADR-0016 accepted, ADR-0004 superseded by ADR-0017, ADR-0005 and ADR-0015 amended, the verification rules marked accepted.
- [x] 0.2 Working agreement: the merge policy in the contribution rules; the answers and assumptions below recorded in the open-questions file; the Android plan, understanding and parity documents retargeted to the new model.
- [x] 0.3 Backend tests runnable locally (section 6): a helper script that wraps the verified steps, and the documented command.
- [x] 0.4 Decision log (`docs/verification-decisions.md`): where every choice the model leaves open is recorded, with date and pull request.

### S1. Specification (on `model/verification`) — 5 pull requests, documents only
- [x] 1.1 Functional requirements (02): replace organisation and vouching requirements with sign-up, vouching, admission, succession, revocation, moving, leaving; keep the provider and searcher requirements.
- [x] 1.2 Data model (03): `people`, `churches`, `home_groups`, `status_changes`, `vouches`, `group_requests`, `admin_invitations`, `handover_requests`, `move_requests`, `notifications`; the fate of each old table; the six invariants as database constraints; indexes.
- [x] 1.3 API (04): the target contract: sign-up, session, `/me`, churches and groups, membership and verifier operations, search, detail, ratings and Reveal by status, notifications. Resource paths for providers and searchers stay (compatibility); authorisation changes to status.
- [x] 1.4 Reports (05), frontend (06), non-functional (07): reports redefined, screens by status, terminology keys, privacy of verifier views (who may see phone numbers and how it is logged), abuse limits for links, notification delivery.
- [x] 1.5 Android documents and parity table rewritten for the new screens (replaces the older phase 3 and 4 descriptions).

### S2. Identity and sign-up — 9 pull requests
Backend first, then web and mobile.
- [x] 2.1 Backend: migration `0007` adds the new identity schema (churches, home groups, people, status history, vouching, requests, notifications) next to the old tables, with the invariants as constraints and one test per rule. **Changed from the first plan** (decision D-20): the old tables are not dropped here, because dropping them would break the working code and tests; each old table is dropped in the pull request that moves its feature (tokens and login history in 2.3, identity tables with 2.6, labels and unavailability in 5.1, ratings and reveals in 5.2), and the last one removes the old identity tables.
- [x] 2.2 Backend: models (done in 2.1) and the permission module (`in_scope`, `can_set_status`, `can_admit`, `can_decline`, `can_vouch`, settable statuses in `app/services/permissions.py`) mirroring the model; one test per invariant (2.1); the permission matrix test (every actor status against every target status and every new status, with the expected answers written out from the rules, checked by mutating the code).
- [x] 2.3 Backend: authentication on the new identity per ADR-0017: one login (email and password, `user_type` optional and defaulting to the person identity), password reset, refresh tokens and login history for people, live status check on every request (`current_person`, and `get_principal` for person tokens). Transitional dual use of the auth tables: decision D-22.
- [x] 2.4 Backend: operator command `create-owner` (the OWNER with the first church and group, one transaction, refused when an OWNER exists; runbook section 9). The operator change of the OWNER moves to 4.5, where it shares its logic with the handover; the older `create-admin` stays until the older accounts go (D-20).
- [x] 2.5 Backend: `GET /me` (person view, readable by a revoked person) and `PUT /me`, and the public, rate-limited list of churches and their home groups with leaders (decision D-19).
- [x] 2.6 Backend: `POST /auth/signup`, `PUT /me/application` (change of choice while pending), the group invitation link (`POST /group-invitations/lookup`, `/verifier/group-invitations`), with the abuse limits of specification 07. Migration `0009` fixes a flaw of 0007 found by the sign-up tests: the people rules checked the row as it was when changed, not as it is at commit. The older register routes and account tables stay until the older accounts go (D-20, S5.2).
- [x] 2.7 Web: sign in (one login, no account type), forgot and reset password for people, the sign-up wizard (also through an invitation link), the home of a person by status (applicant with change of choice and leave, revoked, a placeholder for admitted people), at transitional addresses next to the older pages (specification 06). Backend `DELETE /me` came first (pull request 116).
- [x] 2.8 Mobile: data layer on the new API (`PersonRepository`, `PersonMe`, `Account`), single login (`/sign-in`, no account type), navigation by status (the router sends a person to `/member`; applicant, revoked and admitted screens), sign-up wizard (also through a pasted invitation link), applicant home with change of choice and leave. At transitional addresses next to the older screens, like the web (S2.7).
- [x] 2.9 Slice check: an end-to-end journey test through the real API and database (set up Skills, list churches, sign up by group and by link, log in, read the application, change it, reset a password, leave, join again), which is what the web and the mobile app call (their own tests check the screens against the same contract; a browser and a phone run against the demo are left to the cut-over rehearsal, S6.1); terminology keys for the home group, verifier, admin and owner in the backend and web profiles (D-24; searcher, provider and church are the existing `workhost`, `freelancer` and `organisation` words).

### S3. Trust: vouching and admission — 9 pull requests
- [x] 3.1 Backend: vouch link per applicant; vouch and withdraw; who may vouch; abuse limits and token entropy.
- [x] 3.2 Backend: admit and decline (`canAdmit`), status history, verifier lists (applicants with vouches, members, revoked, flagged); access to phone numbers in scope is logged.
- [x] 3.3 Backend: in-app notifications (outbox, list, mark read) for the events the model names.
- [x] 3.4 Web: vouch page opened from a link; share my vouch link; vouches received and given (withdraw); notifications (top bar count, list, mark read). Browser run: S6.1.
- [ ] 3.5 Web: verifier screens: applicants and vouches, admit and decline, members.
- [x] 3.6 Mobile: share my vouch link; vouch from a received link; notifications list.
- [ ] 3.7 Mobile: verifier screens: applicants and vouches, admit and decline, members.
- [ ] 3.8 Slice check: end-to-end test of apply, collect vouches, admit as searcher and as provider.
- [ ] 3.9 Searcher-to-provider upgrade path.

### S4. Church structure and life cycle — 11 pull requests
- [ ] 4.1 Backend: revoke, reinstate, re-check flags, re-confirm.
- [ ] 4.2 Backend: start a home group (request and approval); invite an ADMIN, which creates a church.
- [ ] 4.3 Backend: succession (step down and replace a leader, hand a group on) with same-transaction guarantees.
- [ ] 4.4 Backend: move between groups by agreement; close a group; close a church. (Leave, which is `DELETE /me` for people who do not lead, was done early for the web applicant home: pull request in S2.7.)
- [ ] 4.5 Backend: OWNER handover; operator change.
- [ ] 4.6 Backend: seeded random-sequence test over all operations checking the invariants after each step.
- [ ] 4.7 Web: revoke and reinstate, flags, group requests.
- [ ] 4.8 Web: ADMIN screens: succession, the church's people and revoked list.
- [ ] 4.9 Web: OWNER screens: churches, invitations, labels management, handover, and the log of phone number views (backend endpoint first; O-03 retention).
- [ ] 4.10 Mobile: revoke and reinstate, flags; ADMIN screens (group requests, succession); close account.
- [ ] 4.11 Slice check: end-to-end tests of a leader leaving, a revocation with flags, and an OWNER handover.

### S5. Product features on the new identity — 14 pull requests
- [ ] 5.1 Backend: provider profile, labels, unavailability owned by the person (paths unchanged).
- [ ] 5.2 Backend: search, detail, ratings and Reveal authorised by status (searcher or above); only admitted providers listed; detail shows church and home group instead of vouching organisations; search performance measured at 10 000 people and 4 000 providers. Closed accounts keep their status as history, so every query and the reveal and rating paths must exclude `closed_at IS NOT NULL`, with a test for a closed provider.
- [ ] 5.3 Backend: reports redefined (verification reports; the Reveal report stays); schedules; demo data generator and seed; OpenAPI export and contract.
- [ ] 5.4 Web: member shell and navigation by status; provider pages (profile, labels, availability, ratings received).
- [ ] 5.5 Web: searcher pages (search, detail, rate, Reveal, ratings given); settings and account.
- [ ] 5.6 Web: old portals removed; responsive and end-to-end tests updated.
- [ ] 5.7 Mobile: provider screens moved to the person endpoints.
- [ ] 5.8 Mobile: search (list, filter sheet, chips, name search, sort, paging).
- [ ] 5.9 Mobile: detail, rate and edit a rating, Reveal (number only in memory, dialler).
- [ ] 5.10 Mobile: ratings given; searcher profile.
- [ ] 5.11 Mobile: settings, privacy link, update hint.
- [ ] 5.12 Mobile: accessibility and parity pass; the parity table reconciled.
- [ ] 5.13 Security review pass: every endpoint against the permission matrix, log review for personal data.
- [ ] 5.14 Documentation pass: runbook (operator procedures, reset of the demo, creating the OWNER), specification reconciled.

### S6. Cut-over — 2 pull requests
- [ ] 6.1 Rehearsal on the integration branch: full CI, end-to-end run, migration on a fresh database; backup and rollback steps in the runbook; the minimum app version raised so old app builds ask to update; release version chosen.
- [ ] 6.2 The pull request `model/verification` into `main` (owner approves), then the demo deploy and smoke test, then a check on a phone.

### S7. Release pipeline (on `main`, may run in parallel) — 4 pull requests
- [ ] 7.1 Web Downloads page (the API already exists).
- [ ] 7.2 `mobile-release` workflow: signed build, upload to the server folder, release asset (owner approves `.github/`).
- [ ] 7.3 Signing and environment documentation (values supplied by the owner as environment secrets).
- [ ] 7.4 Privacy page text (accounts, closure, messages, push tokens).

### S8. Chat and push (after the cut-over) — about 10 pull requests
- [ ] 8.1 Spike: synchronous database layer with an asynchronous socket; two-process notification test; result written down; ADR-0014.
- [ ] 8.2 to 8.4 Chat backend: schema and REST; socket and cross-process delivery; moderation and reports.
- [ ] 8.5 to 8.6 Push: device tokens and outbox; sender.
- [ ] 8.7 to 8.9 Chat in the app: list, thread, reconnect and queue, notification permission, deep links.
- [ ] 8.10 Chat metrics report.

### S9. Hardening and release — 3 pull requests
- [ ] 9.1 Accessibility, performance, battery behaviour of the socket.
- [ ] 9.2 Store data-safety answers and release candidate.
- [ ] 9.3 Staged rollout notes.

Total: about 72 pull requests.

## 5. Risks and how they are handled

| Risk | Handling |
|---|---|
| The model changes while it is being built | It is accepted; open details are decided by default and recorded in the decision log; a change to the model is a visible pull request. |
| The integration branch drifts from `main` | `main` is merged into it regularly; `main` only gets changes that cannot affect the model line. |
| A wrong permission rule is a security hole | Matrix test, invariant tests, random-sequence test, and a review pass before the cut-over. |
| The cut-over breaks the demo | One switch, rehearsed, with a backup and a rollback to the previous image; old app builds are forced to update. |
| Link abuse (guessing, flooding) | Long random tokens stored hashed, expiry, rate limits, nothing revealed about whether a link exists. |
| Verifier screens leak phone numbers | Visible only for people in scope, on verifier screens only, and each view is logged; never in search results. |
| Search is slow at 10 000 people | Measured in 5.2 with the existing performance test pattern. |
| Review comments pile up | Valid ones fixed in the same pull request; the others answered with evidence. |

## 6. Database for the backend tests (verified)

The backend tests need PostgreSQL 16 with the `btree_gist` extension. On the development host this works with the project's own script, which starts `postgres:16-alpine` next to the development container (the host's Docker daemon is shared, and `docker compose` is not installed, so `scripts/ci-postgres.sh` is used):

```
export CI_DB_PASSWORD="$(openssl rand -hex 12)"      # local only, never written to a file in the repository
bash scripts/ci-postgres.sh start                    # prints DB_HOST and DB_PORT
export DATABASE_URL="postgresql+psycopg://skills:${CI_DB_PASSWORD}@<DB_HOST>:<DB_PORT>/skills"
cd backend && uv run pytest -q                       # 208 passed, 1 skipped in about 40 seconds (2026-11-12)
bash scripts/ci-postgres.sh stop
```

Notes: published ports (`127.0.0.1:...`) are not reachable from the development container, but the container's address on the shared network is; a user-level PostgreSQL package without the contrib extensions cannot run the project's migrations. `scripts/backend-tests-local.sh` wraps these steps (S0.3).

## 7. Where the owner is needed

- Once, up front: the answers to the questions in the covering message (defaults are in section 8).
- Making the pull-request tooling usable: sign in to the GitHub command line (or provide a repository-scoped token through the environment, never in a file), and relax the approval rule for the merge policy below.
- Approving the few pull requests that touch `.github/` or `infra/` (about four).
- The cut-over (S6.2): approval and a go-ahead for the demo deploy.
- Later: the app name and application ID before the first signed build; the Firebase project and store accounts before chat and release.
- Optionally: checking the app on a phone at the end of each slice.

## 8. Assumptions (defaults)

1. ADR-0016 is accepted; ADR-0017 replaces ADR-0004.
2. The demo can be wiped and reseeded; there are no real users.
3. `/api/v1` is changed in place; nothing has been released outside internal testing.
4. The platform admin becomes the OWNER; the OWNER manages labels.
5. A person has one account and one status. Work host becomes SEARCHER, freelancer becomes PROVIDER, organisation becomes the church (a structure, not an account).
6. Verifiers see the phone numbers of people in their scope on their own screens only; each view is logged. Search results never show a number.
7. Pictures are deferred (an initials avatar).
8. Notifications are in-app first; email is added when a mail service is chosen; push comes with chat.
9. Chat: any admitted person (searcher or above) may start a conversation with a provider they found; the other side can reply, mute, block and report.
10. OWNER actions are web only; ADMIN and VERIFIER actions are in the app and on the web.
11. Closing an account keeps the trust record and removes the person's personal details; the same flow is the in-app "delete account" that the stores require.
12. Merge policy: pull requests are merged by the assistant once all required checks are green, except those touching `.github/` or `infra/`, which wait for the owner. The demo is deployed only at the cut-over, with the owner's go-ahead.
