# ADR-0005: React and TypeScript frontend

- **Status:** Proposed; the portal structure is amended by [ADR-0016](0016-church-trust-hierarchy-verification-model.md) (see the amendment at the end)
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

The frontend must be React. There are four user interfaces (freelancer, work host, organisation, admin/reports).

## Decision

React 18 with **TypeScript** (strict), **Vite**, React Router, TanStack Query, zod for form validation, and an API client generated from the backend OpenAPI schema. One app with role-based portals sharing a design system.

## Alternatives considered

- Separate apps per user type: more duplication, harder to share components.
- Plain JavaScript: weaker safety against API drift.

## Consequences

- Type errors surface when the API changes.
- Shared components keep the four portals consistent.
- A future React Native app can share API types and some logic.

## Amendment (ADR-0016)

The technology choice above is unchanged. The structure is not: there are no longer four account types with their own portals (freelancer, work host, organisation, admin). A person has one account and one status ([verification model](../verification.md)), and the screens a person sees follow that status: member screens (searching and, for providers, listing skills), verifier screens (applicants, members, revocation), church ADMIN screens and OWNER screens. One app with shared components still applies; the "role-based portals" are status-based sections of it.

