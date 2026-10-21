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

## Tables

### work_hosts
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_email | text NOT NULL | unique, lowercase |
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
| org_name | text NOT NULL | |
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
| status | text NOT NULL default 'approved' | CHECK in (pending, approved, revoked); default depends on Q6 |
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
| level_label_id | uuid FK labels, nullable | only for skill labels; must point to a `skill_level` label (enforced in service layer and a trigger or constraint) |

### freelancer_unavailability
id uuid PK, freelancer_id FK, unavailable_from timestamptz, unavailable_to timestamptz, CHECK (unavailable_from < unavailable_to). Optional exclusion constraint to prevent overlapping periods per freelancer.

### login_history
id uuid PK, user_type text (CHECK freelancer/workhost/organisation/admin), user_id uuid null, login_email text, login_time timestamptz, succeeded boolean, ip_address inet null, user_agent text null.

### user_ratings
id uuid PK, work_host_id FK, freelancer_id FK, rating smallint CHECK (rating BETWEEN 1 AND 10), comment text, rated_on timestamptz, UNIQUE (work_host_id, freelancer_id) (Q5).

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

Seeding is done by a migration so every environment has the same base labels.
