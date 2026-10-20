---
name: skills-marketplace-builder
description: Build or extend "Skills", the freelancer marketplace (freelancers, work hosts, organisations) with a Python FastAPI backend, PostgreSQL, React frontend, reports and scheduled reports. Use when asked to scaffold, implement or extend any part of the Skills app.
---

# Skills marketplace builder

The specification and ADRs in this repository are the source of truth. Read them before writing code; do not duplicate them here.

## Read first

1. `docs/specification/README.md` and the numbered files it lists
2. `docs/adr/README.md` and the accepted/proposed ADRs
3. `docs/open-questions.md` (do not invent answers; use the stated defaults and say so)
4. `CONTRIBUTING.md` (workflow, conventions, definition of done)

## Fixed decisions

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic (ADR-0003)
- Database: PostgreSQL only, UUID keys, `timestamptz` (ADR-0002)
- Auth: bearer JWT + rotating refresh tokens, argon2id, no cookies (ADR-0004)
- Frontend: React 18 + TypeScript + Vite, generated API client (ADR-0005)
- Reports: separate APScheduler worker, `report_runs` table (ADR-0006)
- Layout: `backend/`, `frontend/`, `infra/`, `.github/`, `docs/` in one repo (ADR-0007)
- Demo hosting: Docker Compose on one AWS Lightsail instance (ADR-0008), Terraform (ADR-0009), GitHub Actions + GHCR (ADR-0010). Details in `docs/specification/09-infrastructure.md`

## How to work

1. Follow the phases in `docs/specification/08-delivery-plan.md` in order. Do one phase per branch/PR.
2. Implement against requirement IDs (FR-*, RP-*). Reference them in tests and commit messages.
3. Schema changes only through new Alembic migrations; keep up/down working.
4. If behaviour changes, update the matching specification file in the same change. If a significant technical decision is made, add an ADR from `docs/adr/template.md`.
5. Keep the API mobile-compatible: bearer auth, JSON, no cookies, no redirects, versioned under `/api/v1`.
6. Before finishing: run lint, type check and tests, check the migration up/down, confirm OpenAPI is valid.

## Infrastructure work

- Terraform only under `infra/terraform/`; never click-build or apply from a laptop. No secrets in git.
- Workflows under `.github/workflows/` as listed in section 6 of the infrastructure spec; pin action versions.
- PostgreSQL is never exposed publicly; only the proxy publishes ports 80/443.

## Do not

- Re-add SQLite support without a new ADR.
- Edit an accepted ADR's decision (supersede it instead).
- Log or return password hashes or tokens.
- Guess answers to items in `docs/open-questions.md`.
