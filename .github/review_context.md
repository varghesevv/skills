# Repository Review Brief (common rules)

## 1. What this is
"Skills" is a marketplace for **Freelancers**, **Work hosts** and **Organisations**, supervised by an **Administrator**. Components: `backend/` (FastAPI, PostgreSQL), `frontend/` (React web), `mobile/` (Flutter Android app, later iPhone), `infra/` (Docker, Caddy, Terraform), `.github/` (CI and this reviewer), `docs/`. Web and mobile use the same `/api/v1` API. Runtime: Caddy (TLS, CSP) -> nginx (SPA) / FastAPI (`/api/*`) -> PostgreSQL; APScheduler runs reports.
Per-component rules follow this section when files of that component changed.

## 2. Terminology isolation
Display words (e.g. Church vs Organisation) are installation settings served by the API. **API paths, stored `user_type` values (`freelancer`, `workhost`, `organisation`, `admin`), report names and email schemas never change with wording.** Hard-coding display words in backend models, API routes or client logic is a defect.

## 3. Critical Security Rules (any violation is a Blocker)
1. **Secrets:** no password, token, API key, key store or connection string in code, tests, docs, workflows or config files. Secrets come from environment variables or CI secrets only (ADR-0011).
2. **Logging:** never log credentials, tokens, device tokens, message text or phone numbers. (The demo password-reset link is the one documented exception.)
3. **Authorization (IDOR):** every handler enforces role AND resource ownership. A lookup by id without an owner/participant check is a Blocker. Do not reveal that a resource exists to someone who may not see it (use 404).
4. **Tokens:** HS256 JWT access tokens (15 min), rotating refresh tokens with reuse detection; disabling an account revokes its refresh tokens. Login throttling is keyed by (email, user_type, IP) and the IP comes from trusted proxy headers only.
5. **Untrusted input and output:** validate with Pydantic or typed models; escape user text on output.

## 4. Process invariants
- Admin approves organisations before they can log in; no bypass.
- A freelancer is searchable with at least one skill. A rate or rating is NOT required; requiring either is a regression.
- Only work hosts rate (1-10), one rating per work host and freelancer.
- Search results and profiles never contain email or mobile number. A mobile number is returned only by `POST /freelancers/{id}/reveal-mobile` (work host only, recorded, rate limited).
- The admin has no mobile access.
- New endpoints and screens need tests for unauthorized, wrong-role and wrong-owner cases.
- Specs (`docs/specification/`), the runbook and ADRs are updated in the same PR as the behaviour they describe.
