# 01 Overview

## Vision

Skills helps work hosts find skilled, trusted freelancers quickly, and helps freelancers be found. Organisations add trust by vouching for freelancers.

## Users

| User | Description |
|---|---|
| Freelancer | Offers skilled work (for example plumbing, electrical, networking, patient care, assistance) at an hourly rate. Part-time availability. |
| Work host | Searches for freelancers and provides work. Rates freelancers. Has weekly available days. |
| Organisation | Vouches for freelancers by linking them to the organisation. |
| Admin | Platform operator. Views platform-wide reports and manages labels. (Assumed, see Q1.) |

## Scope

In scope: registration and login for all user types, profiles, labels (skills, languages, timing, nativity, skill level), freelancer availability, search, ratings, organisation vouching, standard and scheduled reports, REST API, React web UI.

Out of scope now: mobile app (the API must remain compatible with it), payments, in-app messaging, job/booking management (see Q4), contracts and invoicing.

## Glossary

- **Label**: a typed tag attached to a freelancer (skill, language, timing, nativity, skill_level).
- **Vouch**: an organisation's link to a freelancer, active or inactive.
- **Unavailability**: a date-time range in which a freelancer cannot work.
- **Timing**: preferred working-hours band such as 06-12 or 24h.
