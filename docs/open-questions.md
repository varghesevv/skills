# Open questions

Decisions still needed from the product owner. When one is answered, record the answer in the relevant specification file (and an ADR if it is architectural), then move it to "Resolved".

## Defaults currently built into the schema

Phase 2 implemented these defaults (change any with a new migration): Q2 `08-06` = 08:00 to 18:00; Q3 skill level per skill; Q5 one editable rating per work host and freelancer; Q6 vouches start `pending` until the freelancer accepts.

## Open

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| Q1 | Is there an admin role for reports and moderation, or do reports belong to organisations only? | Decides who sees platform-wide reports | Seeded admin role (spec assumes this) |
| Q2 | What does timing label `08-06` mean? Should timings be free-form hour ranges instead of fixed labels? | Search filter and label design | Treat as 08:00-18:00 |
| Q3 | Should skill level attach to each skill (plumbing at 80%) or be one level per profile? | Data model of `freelancer_label` | Per skill (spec assumes this) |
| Q4 | Do work hosts create jobs/bookings and hire freelancers in the app, or only search and rate? | There is no job entity; ratings not tied to real work can be abused | Search and rate only |
| Q5 | One rating per work host and freelancer, or one per engagement? | Unique constraint on ratings | One per pair, editable |
| Q6 | Must a freelancer approve an organisation's vouch? | Trust model of vouching | Yes: pending, then approved |
| Q7 | Email provider (SMTP) for password reset and report delivery? Mobile OTP login later? | Auth and notification design | SMTP configured by env |
| Q8 | Time zone for scheduled reports; which currencies are supported? | Report windows, rate display | Asia/Dubai; AED, INR, USD, EUR |
| Q9 | UI languages (English only, or Hindi/Tamil/Malayalam too)? | i18n setup in frontend | English only, i18n-ready |

## Resolved

- **Q10** Database: PostgreSQL only, no SQLite. Confirmed 2026-10-20. See [ADR-0002](adr/0002-postgresql-as-the-only-database.md).

## Open (infrastructure)

| # | Question | Default if unanswered |
|---|---|---|
| Q13 | Who may SSH into the server (office/home IP list)? (owner will provide later) | SSH closed to the world; allow only listed CIDRs |

## Open (existing Lightsail instance, IP 13.233.41.127)

| # | Question | Default if unanswered |
|---|---|---|
| Q15 | Is 13.233.41.127 a Lightsail static IP, or the default public IP? | Treat as default; attach a static IP before DNS is pointed at it |
| Q16 | Instance name, availability zone, OS image (Ubuntu LTS version) and SSH key pair? | Assume Ubuntu 24.04 LTS in `ap-south-1a` |
| Q17 | Current firewall rules (which ports open)? | Restrict to 80/443 only; 22 per Q13 |

## Resolved (infrastructure)

- **Q11** AWS region: `ap-south-1` (Mumbai). Confirmed 2026-10-20.
- **Q12** Domain: the demo uses `skills-demo.privatedir.in`, with DNS in Route 53. Changed 2026-10-22 from `privatedir.com`, whose name servers point to another provider (site4now), so records written to its Route 53 zone were never served. Originally confirmed 2026-10-20.
- **Q14** Production environment: planned within 1 to 2 months after the demo. See section 12 of the [infrastructure spec](specification/09-infrastructure.md) and ADR-0008.
