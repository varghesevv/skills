# ADR-0004: Stateless token auth for web and mobile

- **Status:** Proposed
- **Date:** 2026-10-20
- **Deciders:** Project owner

## Context

The same REST API must serve a JavaScript web app now and a mobile app later. Cookie sessions and redirect-based flows are awkward on mobile.

## Decision

- Bearer **JWT access tokens** (short-lived, about 15 minutes) and **rotating refresh tokens** (about 30 days, stored hashed server-side so they can be revoked).
- Passwords hashed with **argon2id**.
- No cookie sessions; no redirects in auth flows.
- Role claim (`freelancer`, `workhost`, `organisation`, `admin`) in the token; authorisation enforced per endpoint.
- Login attempts throttled and recorded in `login_history`.

## Alternatives considered

- Server sessions with cookies: simple for web, poor fit for mobile.
- Third-party identity provider: possible later; adds cost and dependency now.

## Consequences

- Web and mobile use identical endpoints.
- Access tokens cannot be revoked instantly; short lifetime limits the risk, and refresh tokens can be revoked.
- Web stores the access token in memory, not `localStorage`, to reduce XSS exposure.
