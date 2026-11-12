# Skills

For building or extending the app, follow the project skill `.claude/skills/skills-marketplace-builder/SKILL.md`.

## Verification model

`docs/verification.md` (ADR-0016) is the trust and verification model: OWNER, one ADMIN per church, one leader (VERIFIER) per home group, and SEARCHER and PROVIDER members. Read its **Data model summary** (at the end) before any change that touches people, roles, statuses, membership, vouching or permissions.

- Every such change must follow the model. Where the specification still describes the older organisation-vouching model, the verification model wins.
- If a request conflicts with the model, stop and say so. Do not work around it.
- If the model itself needs to change, update `docs/verification.md` (prose and Data model summary) in the same change, and keep the two consistent.
