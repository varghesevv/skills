# 01 Overview

## Vision

Skills is a closed, high-trust marketplace inside a group of sister churches. It helps members find skilled people they can trust, and helps skilled people be found. Trust comes from the churches' own structure: a person is admitted by the leader of their home group, who knows them, and every change of status records who made it, so each member has a chain of trust back to the top. The rules are in [verification.md](../verification.md) (ADR-0016 and ADR-0017).

## People

| Status | Description |
|---|---|
| Applicant (PENDING) | Has signed up and chosen a church and a home group. Waits to be admitted. Can collect vouches and change the choice; cannot search. |
| Searcher | Admitted. Finds providers, rates them, reveals their mobile number, vouches for applicants. |
| Provider | A searcher who also offers skilled work (for example plumbing, electrical, networking, patient care, assistance) at an hourly rate, with labels and time off, and can be found. |
| Group leader (VERIFIER) | Leads one home group. Admits or declines applicants, revokes and reinstates members, invites people to the group. |
| Church admin (ADMIN) | One per church. Looks after the church's groups and leaders, and runs reports limited to the church. |
| Owner (OWNER) | One per installation. Starts churches (by inviting their admins), manages labels, runs all reports, and can hand the role over. Works on the web only. |
| Revoked | Has no access; sees only why. |

A higher status can do what the lower ones can, plus its own pages. The status is read from the database on every request.

## Scope

In scope: signing up and joining a home group, one login for everyone, admission by group leaders and vouching, profiles with labels (skills, languages, timing, nativity, skill level) and time off, search, ratings, revealing a mobile number (limited and logged), the church structure and its life cycle (group requests, moves, closing a group or a church, handover of a role), standard and scheduled reports, a REST API, a React web app and an Android app.

Out of scope now: payments, in-app messaging, job and booking management (see Q4), contracts and invoicing.

## Glossary

- **Church**: an organisation in Skills. Each has exactly one ADMIN.
- **Home group**: a group within a church, with exactly one leader.
- **Label**: a typed tag attached to a provider (skill, language, timing, nativity, skill_level).
- **Vouch**: a member saying they know an applicant (or a searcher who applies to provide). A vouch counts while the voucher is still admitted.
- **Chain of trust**: who set a person's status, then who set theirs, and so on up to the owner.
- **Unavailability**: a date-time range in which a provider cannot work.
- **Timing**: preferred working-hours band such as 06-12 or 24h.
