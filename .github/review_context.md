# Repository Review Brief & Architecture Rules

## 1. Folder Structure & Runtime Components
- **backend/**: FastAPI application (Python, SQLAlchemy 2, Alembic, Pydantic). Routers in `app/api/v1/`, domain logic in `app/services/`, database models in `app/models/`, schemas in `app/schemas/`.
- **frontend/**: React + TypeScript (Vite) SPA served via nginx. Wording mapping in `src/terminology/`.
- **infra/**: Docker Compose (demo), Caddyfile, and Terraform (AWS Lightsail, S3 backups, OIDC).
- **Runtime Flow**: Caddy (TLS, CSP, reverse proxy) -> nginx (static SPA) / FastAPI (`/api/*`) -> PostgreSQL. APScheduler handles background report generation.

## 2. Core Domain & Terminology Isolation
"Skills" is a marketplace for **Freelancers**, **Work hosts**, and **Organisations**, supervised by an **Administrator**.
- Admin approval gates overall account visibility.
- Display terms (e.g., Church vs. Organisation) are dynamic installation settings. **API paths, database `user_type` values, report names, and email schemas must never change with display terminology.** Hardcoding dynamic terms into backend models or API routes is a defect.

## 3. Critical Security Rules (Any violation is a Blocker)
1. **Secrets:** No hardcoded passwords, tokens, API keys, or connection strings in code, tests, docs, or workflows. Secrets come strictly from environment variables (ADR-0011).
2. **Logging:** No credentials or tokens in log output. (The demo password-reset link in logs is the sole documented exception).
3. **Authorization (IDOR):** Every handler must enforce role AND resource ownership (e.g., a freelancer edits only their own record). Unrestricted object lookups without owner verification are Blockers.
4. **Token Handling:** HS256 JWT access tokens (15m), rotating refresh tokens with family reuse detection. Invalidating account status must immediately revoke refresh tokens.
5. **Login Throttling:** Keyed by `(email, user_type, IP)`. IP must come from trusted proxy headers (Caddy) and not unverified `X-Forwarded-For`.
6. **Frontend Security:** Strict CSP in Caddyfile (`script-src 'self'`). Flag any additions of `unsafe-inline`, `unsafe-eval`, or unescaped `dangerouslySetInnerHTML`.
7. **Input/Output Safety:** Pydantic validates inputs (`page_size` capped at 100). SQLAlchemy expressions only (no raw SQL strings). User free-text must be escaped on output.
8. **Reports:** Validate path handling, recipient addresses, and prevent CSV formula injection (cells starting with `=`, `+`, `-`, `@`).

## 4. Performance & Database Guidelines
- **Search Hot Path:** Query filters must avoid N+1 loads, unbounded results, and `COUNT(*)` over wide joins. Every new filter/sort column requires a matching database index.
- **Aggregates:** Rating aggregates must be computed in SQL, not iterated over in Python per row.
- **Async Safety:** No blocking I/O or synchronous SQLAlchemy calls inside `async def` route handlers.
- **Migrations:** Large table index additions must use `CONCURRENTLY`. Long table-rewriting `ALTER` operations require explicit approval plans.

## 5. Structural Flaws & Process Invariants
- **Layering:** Routers handle HTTP/auth; services contain business rules; models enforce persistence. Business logic placed exclusively in routers or the frontend is a defect.
- **State Machines:** Registration (`pending` -> `approved`/`rejected`), Vouching (`requested` -> `approved`/`revoked`). Flag illegal state transitions, double-submits, or sync mismatches between `status` and `is_active`.
- **Data Integrity:** Database constraints (`UNIQUE`, `FOREIGN KEY`, `CHECK`) are mandatory and must back code-level checks.
- **Time Handling:** Store and compare timezone-aware UTC values (`datetime.now(timezone.utc)`). Never use naive `datetime.utcnow()`.
- **Process Flow Invariants:**
  - Users cannot search, vouch, or rate while in `pending` status.
  - Work hosts can rate freelancers only after a verified engagement.
  - Freelancers must have at least one assigned skill label to appear in search.
  - New endpoints must maintain tests for unauthorized, wrong-role, and wrong-owner cases.