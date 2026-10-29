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

## Open (Android app, see [android/understanding.md](android/understanding.md))

| # | Question | Default if unanswered |
|---|---|---|
| Q-A1 | App name and application ID (cannot change after the first store upload) | Blocking only for the first signed build. Local builds use `com.example.skills.dev` |
| Q-A2 | Which machine builds and runs the app during development? | Answered for now: this server with a phone over wireless debugging, see [android/environment.md](android/environment.md) |
| Q-A3 | May an admin read a conversation? | Only conversations that someone reported, and each access is logged |
| Q-A4 | How long are chat messages kept? | Until either account is deleted, then anonymised; revisit with the privacy page |
| Q-A5 | May a freelancer start a chat after a work host revealed their number? | No (work host starts). Revisit with real usage |
| Q-A6 | Attachments (photos, documents) in chat? | Text only in version 1 |
| Q-A7 | Chat on the web? | Later; the API already supports it |

## Resolved

- **Q10** Database: PostgreSQL only, no SQLite. Confirmed 2026-10-20. See [ADR-0002](adr/0002-postgresql-as-the-only-database.md).

## Open (production, see ADR-0012)

| # | Question | Default if unanswered |
|---|---|---|
| Q18 | Production architecture: ECS Fargate + RDS (ADR-0012 proposal), or a cheaper Lightsail-based option? | ADR-0012 proposal |
| Q19 | Production domain (for example `skills.privatedir.in`) and whether the existing Route 53 zone is reused | `skills.privatedir.in` in the same zone |
| Q20 | Separate AWS account for production, or the same account with separate IAM roles? | Same account, separate roles, until the owner decides |
| Q21 | Email provider for real emails (password reset): Amazon SES, or another SMTP service? | Amazon SES in `ap-south-1` |
| Q22 | Expected number of users and uptime target (decides Multi-AZ, instance sizes, cost)? | Small: single task per service, RDS Multi-AZ on |
| Q23 | Data retention and privacy: how long are ratings, vouches and reports kept, and does the audience include people covered by GDPR or UAE data law? | Keep indefinitely; review before go-live |

## Resolved (infrastructure)

- **Q13** SSH access: only the owner's two addresses (`ssh_allowed_cidrs`, kept in `terraform.tfvars` and the repository variable `TF_SSH_ALLOWED_CIDRS`) plus the Lightsail browser SSH. Deploys open port 22 for the runner and restore this rule afterwards. Resolved 2026-10-22.
- **Q15 to Q17** The existing instance was imported into Terraform (`skills`, `ap-south-1a`, Ubuntu 24.04, key pair `skills-demo`, static IP `13.127.253.202`, ports 80/443 open to the world). Resolved 2026-10-22.
- **Q11** AWS region: `ap-south-1` (Mumbai). Confirmed 2026-10-20.
- **Q12** Domain: the demo uses `skills-demo.privatedir.in`, with DNS in Route 53. Changed 2026-10-22 from `privatedir.com`, whose name servers point to another provider (site4now), so records written to its Route 53 zone were never served. Originally confirmed 2026-10-20.
- **Q14** Production environment: planned within 1 to 2 months after the demo. See section 12 of the [infrastructure spec](specification/09-infrastructure.md) and ADR-0008.
