# ADR-0002: PostgreSQL as the only database

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

The first plan was to support both SQLite and PostgreSQL, each with its own migration scripts. The product is a multi-user marketplace with concurrent writes (registrations, logins, ratings), search across many filters, and scheduled reports reading while users write.

## Decision

Product owner confirmed on 2026-10-20: SQLite support is dropped. Use **PostgreSQL only** for development, test and production. One Alembic migration history. Run PostgreSQL locally with Docker Compose.

## Alternatives considered

- **SQLite and PostgreSQL both:** doubles the test matrix and forces lowest-common-denominator SQL. SQLite lacks real `ALTER TABLE` support (needs batch mode), has a single writer, and treats types loosely, so bugs can pass on SQLite and fail on PostgreSQL. Every contributor would have to keep both working.
- **SQLite only:** simple to start but single-writer and weak for concurrent web traffic, reporting while serving, and growth.

## Consequences

- Better performance and concurrency: row-level locking, a real query planner, proper indexes (partial, composite, trigram), `timestamptz`, `numeric`, native `UUID`, and `CHECK`/enum support.
- Search and reports can use PostgreSQL features (for example `pg_trgm` for name search, `date_trunc` and window functions for reports).
- One migration set, one test target, fewer bugs.
- Contributors need Docker (or a local PostgreSQL) to run the project. We provide `docker compose up db`.
- Tests run against a real PostgreSQL, slightly slower than in-memory SQLite but trustworthy.
- If a lightweight demo mode is ever needed, a new ADR can reintroduce SQLite for that purpose only.
