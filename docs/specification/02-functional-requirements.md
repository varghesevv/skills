# 02 Functional requirements

## Common (all users)

| ID | Requirement |
|---|---|
| FR-C-01 | A user MUST register with email, mobile number and password. Email MUST be unique per user type. Freelancers and work hosts MUST also give their full name (2 to 200 characters); organisations give the Organisation Name instead (2 to 200 characters). |
| FR-C-02 | A user MUST log in with email and password and receive tokens (see API). |
| FR-C-03 | A user MUST be able to reset a forgotten password through a one-time, expiring link sent by email. |
| FR-C-04 | Every login attempt (success or failure) MUST be recorded in login history. |
| FR-C-05 | Repeated failed logins MUST be throttled (default 5 failures per 15 minutes per email and IP). |
| FR-C-06 | A user MUST be able to view and edit only their own profile. |
| FR-C-07 | `last_login_at` MUST be updated on successful login. |

## Freelancer

| ID | Requirement |
|---|---|
| FR-F-01 | Maintain profile: full name, mobile number, WhatsApp availability (yes/no), nationality, primary language. |
| FR-F-02 | Set hourly rate, currency (ISO 4217) and whether the rate is negotiable. |
| FR-F-03 | Select labels: skills (each with a skill level), languages, timings, nativity. |
| FR-F-04 | Add, edit and delete unavailability periods (from < to). |
| FR-F-05 | View own ratings and comments. |
| FR-F-06 | View organisations vouching for them. If Q6 = yes, accept or reject a pending vouch. |
| FR-F-07 | A public profile MUST NOT expose email or password data. A freelancer's mobile number is never part of a profile or search response (see FR-W-08). The full name is shown to logged-in work hosts, organisations and admins, never in the ratings a freelancer receives. |

## Work host

| ID | Requirement |
|---|---|
| FR-W-01 | Maintain profile: full name, mobile number and available days (Sun-Sat). |
| FR-W-02 | Search freelancers (see Search). |
| FR-W-03 | View a freelancer detail page: labels, rate, ratings, vouching organisations, availability. |
| FR-W-04 | Rate a freelancer 1-10 with an optional comment. One rating per work host and freelancer, editable (Q5). |
| FR-W-05 | View ratings they have given. |
| FR-W-06 | Search results and the detail page MUST show a freelancer's mobile number greyed out (a placeholder, not the real number) with a Reveal button. |
| FR-W-07 | Reveal MUST ask the server for the number. On a phone or tablet it then opens the dialler (`tel:`); on a computer it shows the number. The number MUST NOT be in the page source, in any search or profile response, or in any browser cache. |
| FR-W-08 | Only work hosts can reveal. Every reveal MUST be recorded (who, whom, when, phone or computer, page, skills searched). Each work host has an hourly and a daily limit (`REVEAL_MAX_PER_HOUR`, `REVEAL_MAX_PER_DAY`); beyond it the server answers `429` with `Retry-After`. |

## Organisation

| ID | Requirement |
|---|---|
| FR-O-01 | Maintain profile: organisation name, mobile number. |
| FR-O-02 | Vouch for a freelancer (create link) and revoke it (set inactive). |
| FR-O-03 | List vouched freelancers with active status. |
| FR-O-04 | View reports scoped to their own freelancers. |

## Admin

| ID | Requirement |
|---|---|
| FR-A-01 | View all standard reports and scheduled-run history. |
| FR-A-02 | Manage labels (add, rename, deactivate). Labels in use MUST NOT be hard-deleted. |
| FR-A-03 | Trigger a report run manually and download output. |

## Search

| ID | Requirement |
|---|---|
| FR-S-01 | Filter by skill (any/all), skill level, language, timing, nativity. |
| FR-S-02 | Filter by maximum rate, currency and negotiable only. |
| FR-S-03 | Filter by availability on a given date range (excludes overlapping unavailability). |
| FR-S-04 | Filter by vouched by a given organisation, and by minimum average rating. |
| FR-S-05 | Sort by rating, rate, newest. Results MUST be paginated. |
| FR-S-06 | Search MUST show only freelancers who have at least one skill. A rate and ratings are not required, so newcomers are listed. |
