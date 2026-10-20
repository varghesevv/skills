# ADR-0007: Single repository (monorepo)

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

Backend, frontend and documentation change together (an API change needs a client change and a spec change).

## Decision

Keep `backend/`, `frontend/` and `docs/` in one repository.

## Alternatives considered

- Separate repositories: more overhead for cross-cutting changes and release coordination.

## Consequences

- One pull request can change API, client and spec together.
- CI must run only the affected parts to stay fast.
- A future mobile app can live in this repo (`mobile/`) or its own; decide with a new ADR.
