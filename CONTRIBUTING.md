# Contributing to Skills

Several people will work on this project. These rules keep the work consistent.

## Before you start

1. Read the [specification](docs/specification/README.md) and the [ADRs](docs/adr/README.md).
2. Check [open questions](docs/open-questions.md). Do not guess an answer that is still open; raise it.
3. Pick or create an issue. One issue per change.

## Workflow

- Branch from `main`: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- Keep pull requests small and focused. Link the issue and the specification section.
- At least one reviewer approves before merge. Do not merge your own PR.
- Squash-merge with a clear message. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).

## Changing the specification or architecture

- Behaviour change: update the matching file in `docs/specification/` in the same PR as the code.
- Significant technical decision (database, framework, auth model, hosting, data model shape): write a new ADR using [docs/adr/template.md](docs/adr/template.md). Never edit an accepted ADR to change its decision; add a new ADR that supersedes it.

## Code conventions

**Backend (Python)**
- Python 3.12, type hints everywhere, `ruff` for lint and format, `mypy` for types.
- Business logic lives in `services/`, not in routers.
- Every schema change goes through an Alembic migration. Never edit a migration that has been merged; add a new one.
- Never log or return password hashes or reset tokens.

**Frontend (React)**
- TypeScript strict mode, ESLint and Prettier.
- Use the API client generated from the backend OpenAPI schema. Do not hand-write request types.

**Infrastructure (Terraform, Docker, workflows)**
- Changes under `infra/` and `.github/` need review from a CODEOWNER and a passing `ci-infra` plan.
- Never apply Terraform from a laptop against the shared environment; use the `terraform-apply` workflow.
- Never commit secrets, `.env` or `*.tfvars`. Add new settings to the GitHub Environment and document them in `docs/specification/09-infrastructure.md`.
- Pin versions of Terraform providers, GitHub Actions and base images.

## Definition of done

- Code follows the specification; spec updated if behaviour changed.
- Tests added or updated and passing in CI.
- Migration included and reversible if the schema changed.
- OpenAPI schema still valid; no breaking change to `/api/v1` once the mobile app has shipped.
- No secrets committed. Configuration through environment variables.
- Reviewed and approved.

## Security

Report security problems privately to the maintainers, not in a public issue.
