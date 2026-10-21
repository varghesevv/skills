# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

Several people will contribute over time. Without a written record, technical decisions get lost or re-argued.

## Decision

We record significant architecture decisions as ADRs in `docs/adr/`, using the template there.

## Alternatives considered

- Decisions only in chat or issues: hard to find, no stable history.
- A single architecture document: cannot show how decisions changed over time.

## Consequences

Small overhead per decision. New contributors can read the index and understand the reasoning. Accepted ADRs are immutable; changes happen through superseding ADRs.
