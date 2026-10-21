# Skills

Skills is a marketplace for finding skilled freelancers. Three kinds of users take part:

| Entity | Role |
|---|---|
| **Freelancer** | Lists skills, languages, availability and hourly rate. |
| **Work host** | Searches for freelancers, offers work, rates freelancers. |
| **Organisation** | Vouches for freelancers by linking them to the organisation. |

**Status:** phase 1 (scaffold) in progress. Start with the specification.

## Documentation

| Document | Purpose |
|---|---|
| [docs/specification/](docs/specification/README.md) | What we are building: requirements, data model, API, reports, frontend, non-functional requirements |
| [docs/adr/](docs/adr/README.md) | Architecture Decision Records: why we chose what we chose |
| [docs/specification/09-infrastructure.md](docs/specification/09-infrastructure.md) | Demo deployment on AWS Lightsail, Terraform, GitHub Actions |
| [docs/open-questions.md](docs/open-questions.md) | Decisions still needed from the product owner |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute: workflow, conventions, definition of done |

## Quick start (local)

```bash
cp .env.example .env
docker compose up --build      # db, api (http://localhost:8000/docs), worker, web (http://localhost:5173)
```

Backend and frontend details: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).

**Lockfiles still to generate:** the scaffold was written without access to PyPI/npm, so `backend/uv.lock` and `frontend/package-lock.json` do not exist yet. Run `cd backend && uv lock` and `cd frontend && npm install` once, then commit both files. Until then CI and Docker builds resolve versions fresh (not reproducible).

## Planned stack

Python (FastAPI, SQLAlchemy, Alembic), PostgreSQL (only), React + TypeScript, REST API shared by web and a future mobile app. Demo hosting: Docker Compose on one AWS Lightsail instance, provisioned with Terraform, deployed by GitHub Actions. See [ADRs](docs/adr/README.md).

## Planned repository layout

```
backend/     Python REST API, migrations, scheduled report worker
frontend/    React web app (freelancer, work host, organisation, admin portals)
infra/       Terraform, server Docker Compose, deploy and backup scripts
.github/     GitHub Actions workflows, Dependabot, CODEOWNERS
docs/        Specification and ADRs
.claude/     Project skill used by Claude Code for scaffolding and execution
```

## Mobile

A mobile app is planned later and is **out of scope now**. The API is designed so it can be reused without change ([ADR-0004](docs/adr/0004-stateless-token-auth-for-web-and-mobile.md)).
