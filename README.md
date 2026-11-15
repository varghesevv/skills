# Skills

Skills is a trusted marketplace for finding skilled people within a church organisation. Three kinds of people take part, and an **owner** who looks after the installation:

| Entity | Role |
|---|---|
| **Providers** | These list theirs skills, availability and hourly rate. |
| **Searchers** | Who seek a particular set of providers for a job they require doing. |
| **[Verifiers](docs/verification.md)** | Admit searchers and providers within their church. |

**Status:** the application is built (API, web app, Android app, reports) and runs as a demo on AWS. The church trust model is being moved onto the demo from an integration branch (see the [roadmap](docs/roadmap-verification-model.md)). Start with the specification, or jump to [running it on your computer](docs/local-development.md).

## Documentation

| Document | Purpose |
|---|---|
| [docs/local-development.md](docs/local-development.md) | **Run Skills on your computer**: step-by-step guide for beginners (tools to install, start, demo data, tests, troubleshooting) |
| [docs/releasing.md](docs/releasing.md) | Versions, tags and releases: Conventional Commits, release PR, image tags |
| [docs/operations-runbook.md](docs/operations-runbook.md) | Running the demo: deploy, roll back, secrets, backup and restore drill, monitoring |
| [docs/specification/](docs/specification/README.md) | What we are building: requirements, data model, API, reports, frontend, non-functional requirements |
| [docs/adr/](docs/adr/README.md) | Architecture Decision Records: why we chose what we chose |
| [docs/specification/09-infrastructure.md](docs/specification/09-infrastructure.md) | Demo deployment on AWS Lightsail, Terraform, GitHub Actions |
| [docs/verification.md](docs/verification.md) | Verification rules: who can vouch, what searchers and providers need, verifier sign-off |
| [docs/open-questions.md](docs/open-questions.md) | Decisions still needed from the product owner |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute: workflow, conventions, definition of done |

## Licence and use at your own risk

Skills is open source under the [MIT licence](LICENSE). Anyone may download it, run their own instance and change it, on their own terms. It comes **as is, without warranty and without obligation** from the authors. Whoever hosts an instance is responsible for it: its data, its users, its rules and the law that applies to them.

## Quick start (local)

New to the project? Follow the [detailed local development guide](docs/local-development.md). It covers installing the tools on macOS, Windows (WSL) and Linux, starting the application, creating demo data, running the tests and fixing common problems.

If you already have Git, Docker and `make`:

```bash
make env                       # creates .env with random secrets (never commit it)
docker compose up --build      # db, api (http://localhost:8000/docs), worker, web (http://localhost:5173)
```

Backend and frontend details: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).

## Signing in and joining

There is one way in, for everyone:

| Page | Address | For |
|---|---|---|
| Sign in | `/sign-in` | Every person: applicant, searcher, provider, group leader, church admin and the owner. |
| Join | `/sign-up` | A new person: details, a church, a home group (each with its leader's name), and whether to apply as a searcher or a provider. A group's invitation link (`/join/<token>`) skips the church and group steps. |
| Invitation of a church admin | `/invite/<token>` | The person the owner invited to start a church. |

After signing in the app reads who the person is and shows what their **status** allows, under `/member`. Members are admitted by their group leader; leaders are appointed by their church admin and church admins by the owner. The owner, one admin per church and one leader per home group form the chain of trust ([verification rules](docs/verification.md)). The older addresses `/login...` and `/register...` lead to the sign-in and the join pages. Details: [frontend specification](docs/specification/06-frontend.md) and the [local development guide](docs/local-development.md#5-create-demo-data-and-log-in).

## Wording per installation

The words for the three kinds of people (Organisation, Work host, Freelancer) and for the church structure are not fixed. Each installation picks a profile from
[`frontend/src/terminology/profiles.json`](frontend/src/terminology/profiles.json), a plain file of
key/value pairs. `default` keeps today's words; `church` shows Church / Searcher / Provider / Group leader / Church admin / Owner and so on.

- Demo/production: set the Environment variable `TERMINOLOGY_PROFILE` (for example `church`) and deploy.
  The web container hands it to the browser as `/config.json`; no rebuild is needed.
- Local: set `TERMINOLOGY_PROFILE=church` in `.env` and run `make up` again.
- To add a profile, copy a block in `profiles.json` and change the values; a test checks that every
  profile has the same keys.

Only what people see changes. Web addresses (`/sign-in`, `/member/...`), API paths, status values, report file names and emails keep
the original words.

## Stack

Python (FastAPI, SQLAlchemy, Alembic), PostgreSQL (only), React + TypeScript, REST API shared by web and a future mobile app. Demo hosting: Docker Compose on one AWS Lightsail instance, provisioned with Terraform, deployed by GitHub Actions (see [infra/README.md](infra/README.md)). See [ADRs](docs/adr/README.md).

## Repository layout

```
backend/     Python REST API, migrations, scheduled report worker
mobile/      Flutter app for Android (the same login and statuses as the web)
frontend/    React web app (one login; the pages shown depend on the person's status)
infra/       Terraform, server Docker Compose, deploy and backup scripts
.github/     GitHub Actions workflows, Dependabot, CODEOWNERS
docs/        Specification and ADRs
.claude/     Project skill used by Claude Code for scaffolding and execution
```

## Mobile

The Android app lives in [mobile/](mobile/README.md): the same sign-in and the same statuses as the web, with search, provider pages, rating, Reveal, and the leader screens (applicants, members, group requests, moves). It uses the same REST API ([ADR-0004](docs/adr/0004-stateless-token-auth-for-web-and-mobile.md)); the plan is in [docs/mobile-app-plan.md](docs/mobile-app-plan.md) and the screen-by-screen state in the [parity table](docs/android/parity.md).
