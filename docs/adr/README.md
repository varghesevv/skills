# Architecture Decision Records

An ADR records one significant technical decision: the context, the choice, and the consequences. They explain *why* the project looks the way it does, so new contributors do not have to guess or reopen settled questions.

## Rules

- One decision per file, numbered in order: `NNNN-short-title.md`.
- Copy [template.md](template.md).
- Status: `Proposed` -> `Accepted` -> (`Deprecated` or `Superseded by ADR-NNNN`).
- Accepted ADRs are not rewritten. To change a decision, add a new ADR that supersedes the old one and update the old one's status line.
- Discuss in the pull request that adds the ADR.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-postgresql-as-the-only-database.md) | PostgreSQL as the only database | Accepted |
| [0003](0003-python-fastapi-backend.md) | Python FastAPI backend with SQLAlchemy and Alembic | Proposed |
| [0004](0004-stateless-token-auth-for-web-and-mobile.md) | Stateless token auth for web and mobile | Proposed |
| [0005](0005-react-typescript-frontend.md) | React and TypeScript frontend | Proposed |
| [0006](0006-scheduled-reports-in-a-worker-process.md) | Scheduled reports in a separate worker process | Proposed |
| [0007](0007-monorepo.md) | Single repository (monorepo) | Proposed |
| [0008](0008-aws-lightsail-single-instance-demo-deployment.md) | AWS Lightsail single-instance deployment for the demo | Proposed |
| [0009](0009-terraform-for-infrastructure.md) | Terraform for infrastructure | Proposed |
| [0010](0010-github-actions-ci-cd.md) | GitHub Actions for CI/CD and GHCR for images | Proposed |
| [0011](0011-secrets-from-environment-only.md) | Secrets come from the environment only, and are checked before merge | Accepted |
| [0012](0012-production-on-ecs-fargate-and-rds.md) | Production on ECS Fargate and Amazon RDS for PostgreSQL | Proposed |
| [0013](0013-gemini-agent-as-pull-request-reviewer.md) | Gemini agent as an advisory pull request reviewer | Proposed |
| [0015](0015-flutter-for-the-mobile-apps.md) | Flutter for the mobile apps | Proposed |
