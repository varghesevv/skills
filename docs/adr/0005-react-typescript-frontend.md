# ADR-0005: React and TypeScript frontend

- **Status:** Proposed
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
