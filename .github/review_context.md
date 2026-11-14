# Repository Review Brief (common rules)

## 1. What this is
"Skills" is a trust-based marketplace: people belong to a **church** and a **home group**; **searchers** find **providers**. Components: `backend/` (FastAPI, PostgreSQL), `frontend/` (React web), `mobile/` (Flutter), `infra/`, `.github/` (CI and this reviewer), `docs/`. Web and mobile use the same `/api/v1` API. Per-component rules follow when files of that component changed.
Two lines: `main` is deployed to the demo on every merge (only demo-safe changes); `model/verification` carries the church trust model until its cut-over. A PR is one topic, with its tests, and updates the specification, the parity table and the runbook it affects.

## 2. Security (any violation is a Blocker)
1. **Secrets:** none in code, tests, docs, workflows, config, logs or commit/PR text. Secrets come from the environment or CI secrets only (ADR-0011). Test credentials are generated at run time.
2. **Logging:** never log credentials, tokens, device tokens, message text or phone numbers.
3. **Authorization (IDOR):** every handler checks the role AND the person's scope or ownership. Out of scope answers `404`, the same as unknown, so existence is not revealed.
4. **Tokens:** access tokens carry only the person id (the model line) and the status is read from the database on every request. Refresh tokens rotate with reuse detection, and disabling or closing an account revokes them. Login throttling is keyed by (email, IP) with the IP from trusted proxy headers only. Link and invitation tokens are stored hashed, shown once, sent in request bodies (never in API paths or query keys), and every failure gives the same `404`. The demo password-reset link in the log is the one documented exception to the logging rule.
5. **Phone numbers:** returned only by the reveal endpoint, except the leader views (`GET /verifier/people/{id}`), which log each view. Lists, search results and notifications never carry a number or an email.
6. **Untrusted input and output:** validate with Pydantic or typed models; escape user text on output.

## 3. The verification model (`docs/verification.md`, ADR-0016; it wins over older specs)
Statuses: revoked < pending < searcher < provider < verifier < admin < owner. Any change to people, roles, statuses, membership, vouching or permissions follows it, or updates `docs/verification.md` (prose and Data model summary) in the same PR. A violation is a **Blocker**:
- Exactly one OWNER; every open church has exactly one ADMIN (the OWNER in their own); every open home group has exactly one leader who belongs to it and leads no other; every VERIFIER leads their own group.
- Nobody stops leading a group or church without a successor (a member, PENDING or above) appointed in the same transaction, or the group or church closing.
- Status changes follow scope and permission rules: only people below you, in your scope; never your own; no overriding a revocation or appointment by a higher leader.
- Every status change is written to the append-only history with who made it. Accounts, groups and churches are closed (`closed_at`), never deleted.
- Revoking a leader flags, but does not change, everyone whose current status they set.

## 4. Project conventions (the first two are rules to enforce; the rest are not to be reported)
- Role words (church, home group, provider ...) come from the server (`GET /api/v1/app/config`); API paths, stored values and report names never change with wording. A client that hard-codes a role word is a defect.
- `datetime.now(UTC)` set explicitly on history rows is the convention of the trust services (rows of one transaction need an order); do not ask for `utc_now()`.
- Services lock people by id first, then home groups, then churches, and re-check after the locks; a read before the lock that is checked again after it is the pattern, not a race.
- Conventional Commit PR titles (release-please). No tool or assistant name, "generated with" line or co-author trailer in titles, bodies or commits: report one if you see it.
- Formatting, import order and naming are enforced by linters; do not comment on them.

## 5. Process
- New endpoints and screens need tests for unauthorized, wrong-role and out-of-scope cases, and for loading, empty and error states.
- The OpenAPI file (`docs/openapi.json`) is generated; the specification, ADRs and runbook change in the same PR as the behaviour.
- A PR that touches `.github/` or `infra/` waits for the owner.

## 6. Until the cut-over
PRs on `main` still serve the older organisation model, whose rules apply to them: the admin approves organisations before they log in; a freelancer is searchable with at least one skill (no rate or rating is required); only work hosts rate (1-10), once per freelancer; the mobile number is returned only by `POST /freelancers/{id}/reveal-mobile` (work host only, recorded, rate limited); the admin has no mobile access. PRs on `model/verification` follow sections 2 to 5 instead; the old-model code is removed at the cut-over (S6).
