# Skills

Skills is a trusted marketplace for finding skilled people within a church organisation. Three kinds of people take part:

| Entity | Role |
|---|---|
| **Providers** | These list theirs skills, availability and hourly rate. |
| **Searchers** | Who seek a particular set of providers for a job they require doing. |
| **[Verifiers](verification.md)** | Vouches for providers and searches within their church. |

**Status:** the application is built (API, web portals, reports) and runs as a demo on AWS. Start with the specification, or jump to [running it on your computer](docs/local-development.md).

## Documentation

| Document | Purpose |
|---|---|
| [docs/local-development.md](docs/local-development.md) | **Run Skills on your computer**: step-by-step guide for beginners (tools to install, start, demo data, tests, troubleshooting) |
| [docs/releasing.md](docs/releasing.md) | Versions, tags and releases: Conventional Commits, release PR, image tags |
| [docs/operations-runbook.md](docs/operations-runbook.md) | Running the demo: deploy, roll back, secrets, backup and restore drill, monitoring |
| [docs/specification/](docs/specification/README.md) | What we are building: requirements, data model, API, reports, frontend, non-functional requirements |
| [docs/adr/](docs/adr/README.md) | Architecture Decision Records: why we chose what we chose |
| [docs/specification/09-infrastructure.md](docs/specification/09-infrastructure.md) | Demo deployment on AWS Lightsail, Terraform, GitHub Actions |
| [docs/open-questions.md](docs/open-questions.md) | Decisions still needed from the product owner |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute: workflow, conventions, definition of done |

## Quick start (local)

New to the project? Follow the [detailed local development guide](docs/local-development.md). It covers installing the tools on macOS, Windows (WSL) and Linux, starting the application, creating demo data, running the tests and fixing common problems.

If you already have Git, Docker and `make`:

```bash
make env                       # creates .env with random secrets (never commit it)
docker compose up --build      # db, api (http://localhost:8000/docs), worker, web (http://localhost:5173)
```

Backend and frontend details: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).

## Login pages

There are three separate login pages. Each one is for one kind of account, so the page decides which account is used:

| Page | Address | For |
|---|---|---|
| Log in | `/login` and `/login/workhost` | Freelancers and work hosts. Two links at the top of the form (**Freelancer**, **Work host**) switch between them. |
| Organisation log in | `/login/organisation` | Organisations only. A new organisation can log in once an admin has approved it. Share this address directly; the main login page does not link to it. |
| Admin log in | `/login/admin` | Administrators only. There is no sign-up; operators create admins. Share this address directly; no page links to it. |

Opening a protected address while logged out leads to the matching login page. Old `/login?type=...` links are redirected. Details: [frontend specification](docs/specification/06-frontend.md) and the [local development guide](docs/local-development.md#5-create-demo-data-and-log-in).

## Wording and web addresses per installation

The words for the three kinds of people (Organisation, Work host, Freelancer) and the matching web
addresses are not fixed. Each installation picks a profile from
[`frontend/src/terminology/profiles.json`](frontend/src/terminology/profiles.json), a plain file of
key/value pairs. `default` keeps today's words; `church` shows Church / Provider / Freelancer and
uses `/church`, `/login/church`, `/provider` and so on.

- Demo/production: set the Environment variable `TERMINOLOGY_PROFILE` (for example `church`) and deploy.
  The web container hands it to the browser as `/config.json`; no rebuild is needed.
- Local: set `TERMINOLOGY_PROFILE=church` in `.env` and run `make up` again.
- To add a profile, copy a block in `profiles.json` and change the values; a test checks that every
  profile has the same keys.

Only what people see changes. API paths, stored `user_type` values, report file names and emails keep
the original words.

## Stack

Python (FastAPI, SQLAlchemy, Alembic), PostgreSQL (only), React + TypeScript, REST API shared by web and a future mobile app. Demo hosting: Docker Compose on one AWS Lightsail instance, provisioned with Terraform, deployed by GitHub Actions (see [infra/README.md](infra/README.md)). See [ADRs](docs/adr/README.md).

## Repository layout

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
