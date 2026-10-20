# Skills: Specification

Version 0.1 (draft). Single source of truth for what Skills must do. Technical reasoning is in [../adr/](../adr/README.md). Unresolved points are in [../open-questions.md](../open-questions.md).

| # | File | Contents |
|---|---|---|
| 01 | [overview.md](01-overview.md) | Vision, users, scope, glossary |
| 02 | [functional-requirements.md](02-functional-requirements.md) | What each user type can do |
| 03 | [data-model.md](03-data-model.md) | PostgreSQL schema, constraints, seed data |
| 04 | [api.md](04-api.md) | REST API conventions and endpoints |
| 05 | [reports.md](05-reports.md) | Standard reports and scheduled generation |
| 06 | [frontend.md](06-frontend.md) | React portals and pages |
| 07 | [non-functional.md](07-non-functional.md) | Security, performance, testing, operations |
| 08 | [delivery-plan.md](08-delivery-plan.md) | Phases and definition of done |
| 09 | [infrastructure.md](09-infrastructure.md) | AWS Lightsail demo, Terraform, Docker, GitHub Actions CI/CD, backups |

Requirement IDs (for example `FR-F-03`) are stable: use them in issues, PRs and tests.
Keywords MUST, SHOULD, MAY follow RFC 2119.
