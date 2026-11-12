# ADR-0016: Church trust hierarchy as the verification model

- Status: Accepted (2026-11-12, project owner)
- Date: 2026-11-12
- Deciders: Project owner

## Context

Skills is a closed, high-trust community spanning several churches, with about 10,000 users of whom at least 4,000 are providers. Churches keep no formal membership roll, so trust has to come from people who know each other.

The current [specification](../specification/README.md) admits people through organisations vouching for freelancers and an administrator approving organisations. That model does not match how a church works: the minister knows the home group leaders, and they know the people in their groups. It also leaves no recorded chain of trust for each member, and no rule for what happens when a leader leaves or breaches trust.

[docs/verification.md](../verification.md) sets out a replacement, agreed with the product owner in November 2026.

## Decision

Adopt [docs/verification.md](../verification.md) as the trust and verification model for Skills: an OWNER, one ADMIN per church, one leader (VERIFIER) per home group, and SEARCHER and PROVIDER members, with a single status ladder, same-step succession, bottom-up group growth and a permanent status history. Every feature that touches people, roles, statuses, membership, vouching or permissions must follow it, or change it in the same pull request.

## Alternatives considered

- **Keep the current organisation-vouching model.** It needs a central administrator to approve organisations, records no chain of trust per person, and does not reflect how churches are organised.
- **A flat model with only administrators and members.** Simpler, but puts all verification on a few administrators and loses the personal knowledge home group leaders have.
- **Top-down appointment of every group and leader by the ADMIN.** Rejected in favour of bottom-up growth: members start groups and leaders bring people in, while the layers above only approve. This keeps the load on ADMINs and the OWNER light.

## Consequences

- The specification must be updated before the model is built: roles, functional requirements, data model, API and reports. This includes mapping the new statuses to the stored `user_type` values, which the review brief says never change with wording, and mapping churches to organisations.
- Status changes must go through a single permissions module that mirrors `canSetStatus` and `canAdmit` in the [Data model summary](../verification.md#data-model-summary).
- The invariants (one OWNER, one ADMIN per open church, one leader per open home group, same-step succession) should be enforced by database constraints and covered by tests named after each invariant, so a change that breaks the model fails CI.
- Closed accounts, groups and churches are kept with a `closedAt` date, not deleted, so the chain of trust stays intact. This changes the current delete-cascade behaviour in the data model.
- The automated reviewer brief, the project skill, `CLAUDE.md` and the pull request template point to the model, so new work is checked against it.
