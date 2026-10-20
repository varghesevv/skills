# 08 Delivery plan

Work in phases. Each phase ends with passing tests, updated docs and a reviewed merge.

| Phase | Scope | Exit criteria |
|---|---|---|
| 1 Scaffold | Repo layout, Dockerfiles, local Docker Compose (PostgreSQL), lint/format, CI workflows (`ci-backend`, `ci-frontend`, `ci-docs`), config | `docker compose up` starts API with `/health`; CI green on a pull request |
| 2 Database | Models, Alembic migrations, label seed | Migration up and down passes in CI |
| 3 Auth | Registration, login, refresh, logout, password reset, login history, throttling | FR-C-01 to FR-C-07 tested |
| 4 Core APIs | Profiles, labels, unavailability, vouching, ratings | FR-F, FR-W, FR-O tested |
| 5 Search | Filters, sorting, pagination, indexes | FR-S tested, performance target checked |
| 6 Reports | Report registry, standard reports, worker, scheduled daily report, run history | RP-01 to RP-07 and the daily report run on schedule |
| 7 Frontend | Shell and auth, then each portal, report pages | All portals cover their functional requirements |
| 7b Infrastructure | Terraform bootstrap and `envs/demo`, server compose file, cloud-init, backup scripts, `build-images`, `terraform-apply`, `deploy-demo` workflows (see [09](09-infrastructure.md)). Can start in parallel with phase 4 | Demo URL reachable over HTTPS; deploy from `main` works; backup restore drill done |
| 9 Production readiness | Decide production architecture (ADR), add `envs/prod`, production checklist (infrastructure spec section 12). Planned 1 to 2 months after the demo | Production ADR accepted; checklist complete |
| 8 Hardening | Security review, rate limits, docs, deployment guide | Non-functional requirements met |

## Definition of done (release 1)

- All functional requirements implemented and tested.
- Migrations apply and roll back on PostgreSQL.
- Every endpoint in OpenAPI; no cookies required.
- Daily "users registered in the last day" report runs on schedule and is visible in the UI.
- README explains setup, environment variables and running the worker.
- Demo environment deployed and reachable via the pipeline (section 11 of the infrastructure spec).
- Open questions Q1-Q9 and Q13 resolved and reflected here.
