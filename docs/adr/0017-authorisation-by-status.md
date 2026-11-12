# ADR-0017: Authorisation by status

- Status: Proposed
- Date: 2026-11-12
- Deciders: Project owner

Supersedes [ADR-0004](0004-stateless-token-auth-for-web-and-mobile.md).

## Context

[ADR-0004](0004-stateless-token-auth-for-web-and-mobile.md) chose bearer tokens for web and mobile, and put a role claim (`freelancer`, `workhost`, `organisation`, `admin`) in the access token. It accepted that "access tokens cannot be revoked instantly".

The [verification model](../verification.md) ([ADR-0016](0016-church-trust-hierarchy-verification-model.md)) changes both points. A person has one account and one status on a single ladder (PENDING, SEARCHER, PROVIDER, VERIFIER, ADMIN, OWNER; REVOKED below them), and other people change that status. A revocation is a breach of trust, so it must take effect at once, not when a token expires. Authority also depends on the person's church and home group, which can change, so a claim copied into a token goes stale.

## Decision

Keep from ADR-0004:

- Bearer **JWT access tokens**, short-lived (about 15 minutes), and **rotating refresh tokens** (about 30 days, stored hashed so they can be revoked).
- Passwords hashed with **argon2id**.
- No cookie sessions and no redirects in auth flows.
- Login attempts throttled and recorded in the login history.
- On the web the access token stays in memory.

Change:

- The access token identifies the **person only** (its subject is the person id). It carries **no role and no status**.
- On every authenticated request the API loads the person (status, closed flag, church, home group) from the database and authorises with the permission module of the verification model (`canSetStatus`, `canAdmit`, scope). A REVOKED or closed account is refused immediately, and its refresh tokens are revoked.
- Clients learn the person's status from `GET /me`, never from the token.

## Alternatives considered

- **Keep a status claim in the token with a short lifetime.** A revoked person would keep access for up to 15 minutes. Not acceptable for a breach of trust.
- **Cache the status with invalidation.** More moving parts for no measured need. Revisit only if the per-request read shows up in measurements.
- **Server sessions.** Still a poor fit for mobile (as in ADR-0004).

## Consequences

- One primary-key read per authenticated request; it is cheap and can be cached later.
- A revocation or closure takes effect on the next request. This removes the accepted weakness of ADR-0004 for permissions.
- Tokens are smaller and nothing in them can go stale.
- The `user_type` login field, the `user_type` claim and the per-type email uniqueness in the current implementation go away with the migration to the model; the specification (API, data model) is updated before that is built, as ADR-0016 requires.
