# 03 Data model (PostgreSQL)

Decision: PostgreSQL only, SQLite is not supported (confirmed 2026-10-20, [ADR-0002](../adr/0002-postgresql-as-the-only-database.md)). Migrations: Alembic, one history, in `backend/migrations/`.

## Conventions

- Table names plural snake_case. Primary keys: `uuid` (default `gen_random_uuid()`), so ids are not guessable and are safe to expose to web and mobile.
- Timestamps: `timestamptz`, stored in UTC, columns `created_at` and `updated_at` (`updated_at` maintained by the application or trigger).
- Emails stored lowercase; uniqueness on `lower(user_email)` (or `citext`).
- Enumerated values use `text` with `CHECK` constraints (easy to migrate).
- Never store plain passwords or plain reset tokens.

## Corrections to the original proposal

- Typos fixed: `last_udpdated_at` -> `updated_at`, `unavalable_from` -> `unavailable_from`, `freelance_id` -> `freelancer_id`.
- `part_time_freelancers` -> `freelancers`.
- `forget_password_hash` columns replaced by one `password_reset_tokens` table (expiry, single use).
- `skill_level` added to the label type list (it was used but not listed).
- `login_history` gains `user_id`, `ip_address`, `user_agent`; column `succeed` -> `succeeded`.
- Skill level is attached per skill via `freelancer_labels.level_label_id` (Q3).

## Implementation status

Implemented in phase 2: models in `backend/app/models/`, migration `0001` (schema) and `0002` (seed labels and report schedules) in `backend/migrations/versions/`. Tests in `backend/tests/` run against a separate database (`skills_test`) and check every rule below.

Delete behaviour: deleting a freelancer removes their labels, unavailability, vouches and ratings (`ON DELETE CASCADE`); deleting a work host removes the ratings they gave; labels in use cannot be deleted (`RESTRICT`); `login_history` has no foreign keys so history survives account deletion. Other rules: `rate_per_hour` and `rate_currency` must both be set or both empty; currency is three upper-case letters.

## Tables

### work_hosts
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_email | text NOT NULL | unique, lowercase |
| full_name | varchar(200) | required at registration; empty only for accounts created before names existed |
| mobile_number | text NOT NULL | E.164 format |
| password_hash | text NOT NULL | argon2id |
| avail_sun .. avail_sat | boolean NOT NULL default false | seven columns, one per day |
| created_at, updated_at | timestamptz NOT NULL | |
| last_login_at | timestamptz | |

### freelancers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_email | text NOT NULL | unique, lowercase |
| full_name | varchar(200) | required at registration; empty only for accounts created before names existed |
| mobile_number | text NOT NULL | E.164 |
| whatsapp_availability | boolean NOT NULL default false | |
| password_hash | text NOT NULL | |
| nationality | text | |
| primary_language | text | |
| rate_per_hour | numeric(10,2) | CHECK >= 0 |
| rate_currency | char(3) | ISO 4217 |
| is_rate_negotiable | boolean NOT NULL default false | |
| created_at, updated_at, last_login_at | timestamptz | |

### organisations
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| org_name | text NOT NULL | shown as "Organisation Name" |
| approval_status | text NOT NULL | `pending` (default), `approved`, `rejected`. Only approved organisations can log in |
| approved_at, approved_by_admin_id | timestamptz, uuid FK admins | set when an admin decides |
| user_email | text NOT NULL | unique, lowercase |
| mobile_number | text NOT NULL | |
| password_hash | text NOT NULL | |
| created_at, updated_at, last_login_at | timestamptz | |

### admins
Same shape as work_hosts without availability: id, user_email, password_hash, created_at, updated_at, last_login_at. Seeded by CLI, never self-registered.

### org_freelancers
| Column | Type | Notes |
|---|---|---|
| org_id | uuid FK organisations | PK part |
| freelancer_id | uuid FK freelancers | PK part |
| is_active | boolean NOT NULL default true | |
| status | text NOT NULL default 'pending' | CHECK in (pending, approved, revoked). A vouch starts pending until the freelancer accepts (Q6 default) |
| created_at | timestamptz | |

### labels
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| label_name | text NOT NULL | |
| label_type | text NOT NULL | CHECK in (skill, language, timing, nativity, skill_level) |
| is_active | boolean NOT NULL default true | |
| | | UNIQUE (label_type, label_name) |

### freelancer_labels
| Column | Type | Notes |
|---|---|---|
| freelancer_id | uuid FK | PK part |
| label_id | uuid FK labels | PK part |
| level_label_id | uuid FK labels, nullable | only for skill labels; must point to a `skill_level` label. Enforced by the database trigger `freelancer_labels_level_check` (migration 0001) and a CHECK that it differs from `label_id` |

### freelancer_unavailability
id uuid PK, freelancer_id FK, unavailable_from timestamptz, unavailable_to timestamptz, CHECK (unavailable_from < unavailable_to). An exclusion constraint (`btree_gist` extension) prevents overlapping periods for the same freelancer; back-to-back periods are allowed.

### login_history
id uuid PK, user_type text (CHECK freelancer/workhost/organisation/admin), user_id uuid null, login_email text, login_time timestamptz, succeeded boolean, ip_address inet null, user_agent text null.

### user_ratings
id uuid PK, work_host_id FK, freelancer_id FK, rating smallint CHECK (rating BETWEEN 1 AND 10), comment text, rated_on timestamptz, updated_at timestamptz null (set when the rating is edited), UNIQUE (work_host_id, freelancer_id) (Q5).

### password_reset_tokens
id uuid PK, user_type text, user_id uuid, token_hash text, expires_at timestamptz, used_at timestamptz null.

### refresh_tokens
id uuid PK, user_type text, user_id uuid, token_hash text, expires_at timestamptz, revoked_at timestamptz null, created_at timestamptz, replaced_by uuid null (rotation).

### report_schedules and report_runs
- `report_schedules`: id, report_name, cron_expression, timezone, is_enabled, recipients (text).
- `report_runs`: id, report_name, window_from, window_to, started_at, finished_at, status (running/succeeded/failed), file_path, row_count, error_message. UNIQUE (report_name, window_from, window_to) for idempotency.

## Indexes

`lower(user_email)` on each user table; `labels(label_type, label_name)`; `freelancer_labels(label_id)`; `user_ratings(freelancer_id)`; `login_history(login_time)`, `login_history(login_email, login_time)`; `created_at` on all user tables (reports); `freelancer_unavailability(freelancer_id, unavailable_from, unavailable_to)`.

## Seed data (labels)

| Type | Values |
|---|---|
| skill | plumbing, electrical, networking, patientcare, assistance |
| timing | 06-12, 08-06, 20-24, 24h (meaning of 08-06: Q2) |
| language | English, Hindi, Tamil |
| nativity | Indian, Srilankan, Keralite, Bangla, Philippines |
| skill_level | basic, 50%, 80% |

Seeding is done by migration `0002` so every environment has the same base labels. The same migration seeds `report_schedules`: `users_registered_daily` (`5 0 * * *`), `weekly_summary` (`0 6 * * 1`), `monthly_summary` (`0 6 1 * *`), timezone Asia/Dubai.
