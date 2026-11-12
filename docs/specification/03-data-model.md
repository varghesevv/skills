# 03 Data model (PostgreSQL)

Decision: PostgreSQL only, SQLite is not supported (confirmed 2026-10-20, [ADR-0002](../adr/0002-postgresql-as-the-only-database.md)). Migrations: Alembic, one history, in `backend/migrations/versions/`.

This file describes the **target** schema of the church trust model ([verification rules](../verification.md), [ADR-0016](../adr/0016-church-trust-hierarchy-verification-model.md), [ADR-0017](../adr/0017-authorisation-by-status.md)). The new identity tables are added by migration `0007` (slice S2.1) next to the old ones (decision D-20); each old table is dropped in the pull request that moves its feature, and the demo data is wiped at the cut-over (decision D-03). Until then the code still has the older schema (work hosts, freelancers, organisations, admins); the table "Fate of the old tables" shows how each maps and which roadmap item drops it.

## Implementation status

Migration `0007` creates the tables of this file that belong to the new identity (`churches`, `home_groups`, `people`, `status_changes`, `vouches`, `vouch_links`, `group_invitations`, `group_requests`, `admin_invitations`, `handover_requests`, `move_requests`, `notifications`, `contact_views`) with all constraints of "The six invariants as database constraints", CHECKs that stop a request or invitation having two outcomes (and clear an invitation's email once it is decided), a composite foreign key that ties `last_home_group_id` to the person's church, triggers that keep a move inside one church and restrict vouches, and the functions `status_rank`, `check_church_rules` and `check_group_rules`. It leaves the old tables in place (decision D-20); the tables that still point at the old accounts (`person_labels`, `person_unavailability`, `ratings`, `phone_reveals`, `login_history`, `password_reset_tokens`, `refresh_tokens`) move in the pull requests named in the roadmap. Tests: `backend/tests/test_trust_schema.py`, one per rule, using `SET CONSTRAINTS ALL IMMEDIATE` to check at once what PostgreSQL checks at commit.

## Conventions

- Table names plural snake_case. Primary keys: `uuid` (default `gen_random_uuid()`), so ids are not guessable and are safe to expose to web and mobile.
- Timestamps: `timestamptz`, stored in UTC, columns `created_at` and `updated_at` where a row changes.
- Emails stored lowercase; uniqueness on `lower(email)`.
- Enumerated values use `text` with `CHECK` constraints (easy to migrate). Statuses are ordered by the SQL function `status_rank(text)` (revoked 0, pending 1, searcher 2, provider 3, verifier 4, admin 5, owner 6).
- Never store plain passwords, plain reset tokens or plain link tokens: store hashes.
- Closing is never deleting: rows of people, groups and churches stay, with `closed_at` set.
- Personal data (name, email, mobile number, password hash) is held on `people` and is cleared when the account is closed. Other tables hold ids, never copies. Two tables hold a little more and are the named exceptions: `login_history` (email, address and browser of attempts; cleared for a person's rows when their account is closed) and `admin_invitations` (the invited email, cleared when the invitation is accepted, cancelled or expired). Retention of both is open detail O-07.

## Fate of the old tables

| Old table | Fate | Dropped or changed by |
|---|---|---|
| `work_hosts`, `freelancers` | Replaced by `people` (one account, one status). A work host's available days are dropped: the model has no use for them. | Sign-up on `people` is S2.6; the table is removed with the last older account type (S5.2) |
| `organisations`, `org_freelancers` | Dropped. The church is a structure (`churches`, `home_groups`); vouching is `vouches`. | S5.2, with the older routes that use them |
| `admins` | Dropped. The platform admin is the OWNER, a row in `people`. | S5.2; the `create-owner` command exists since S2.4 |
| `labels` | Kept unchanged. | |
| `freelancer_labels` | Renamed `person_labels`, key `person_id`. | S5.1 |
| `freelancer_unavailability` | Renamed `person_unavailability`, key `person_id`. | S5.1 |
| `user_ratings` | Kept as `ratings`, with `rater_id` and `provider_id` pointing at `people`. | S5.2 |
| `phone_reveals` | Kept, with `revealer_id` and `provider_id`. | S5.2 |
| `login_history` | Kept; `user_type` dropped, `person_id` added. | S2.3 accepts `person` in `user_type` (migration 0008), the person's id goes in `user_id`; the column is dropped with the last older account type (S5.2) |
| `password_reset_tokens`, `refresh_tokens` | Kept; `user_type` dropped, key `person_id`. | Same as `login_history` |
| `report_schedules`, `report_runs` | Kept; the report set changes. | S5.3 |

The last pull request that removes an old table also removes the old identity tables, so the old and the new identity never coexist at the cut-over.

## Tables

### churches
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | varchar(200) NOT NULL | unique among open churches (`lower(name)`, `WHERE closed_at IS NULL`) |
| admin_id | uuid NOT NULL FK people | `DEFERRABLE INITIALLY DEFERRED`; the church's ADMIN, or the OWNER in the OWNER's own church |
| created_at | timestamptz NOT NULL | |
| closed_at | timestamptz | set when the OWNER closes the church; the row and its revoked list are kept |

### home_groups
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| church_id | uuid NOT NULL FK churches | UNIQUE (id, church_id) so `people` can reference both |
| name | varchar(200) NOT NULL | unique per church among open groups |
| leader_id | uuid NOT NULL FK people | `DEFERRABLE INITIALLY DEFERRED`. A person leads at most one open group: `EXCLUDE USING btree (leader_id WITH =) WHERE (closed_at IS NULL) DEFERRABLE INITIALLY DEFERRED`. A closed group keeps its last leader as history only |
| created_at | timestamptz NOT NULL | |
| closed_at | timestamptz | set when the group is closed |

### people
One row per person, whatever their status.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| status | text NOT NULL | CHECK in (revoked, pending, searcher, provider, verifier, admin, owner) |
| church_id | uuid NOT NULL FK churches | revoked people stay on their church's revoked list |
| home_group_id | uuid FK home_groups | NULL if and only if the person is revoked or closed (the CHECK below); composite FK (home_group_id, church_id) to `home_groups (id, church_id)` |
| last_home_group_id | uuid FK home_groups | set on revocation: the group they were removed from, so its leader keeps them in scope |
| full_name | varchar(200) | 2 to 200 characters; NULL only when closed |
| email | text | lowercase; NULL only when closed |
| mobile_number | text | E.164; NULL only when closed |
| password_hash | text | argon2id; NULL only when closed |
| requested_status | text | CHECK in (searcher, provider); what the applicant applies for, also set when a searcher applies to provide |
| status_set_by_id | uuid FK people | who set the current status; NULL for new applicants, the first OWNER, and an OWNER appointed by the operators |
| flagged_for_recheck | boolean NOT NULL default false | set when whoever set their current status is revoked |
| whatsapp_availability | boolean NOT NULL default false | provider profile |
| nationality, primary_language | text | provider profile |
| rate_per_hour | numeric(10,2) | CHECK >= 0 |
| rate_currency | char(3) | ISO 4217; with `rate_per_hour` both set or both empty |
| is_rate_negotiable | boolean NOT NULL default false | |
| created_at, updated_at | timestamptz NOT NULL | |
| last_login_at | timestamptz | |
| closed_at | timestamptz | set when the account is closed; personal fields are cleared in the same statement |

The picture is not stored; clients draw an initials avatar (decision D-08).

### status_changes
Permanent, append-only history. The chain of trust is built from it.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| person_id | uuid NOT NULL FK people | |
| from_status | text | NULL at account creation |
| to_status | text NOT NULL | |
| changed_by_id | uuid FK people | NULL if and only if `kind` is `signup` or `operator` (an operator change in the database); CHECK (changed_by_id IS DISTINCT FROM person_id OR kind = 'handover'), because nobody changes their own status except the OWNER in a handover |
| kind | text NOT NULL | CHECK in (signup, admit, appoint, step-down, revoke, reinstate, reconfirm, handover, operator) |
| at | timestamptz NOT NULL | |

A trigger refuses `UPDATE` and `DELETE` on this table. `people.status_set_by_id` is the `changed_by_id` of the latest row, so both are NULL for a new applicant.

### vouches
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| applicant_id | uuid NOT NULL FK people | a PENDING applicant, or a SEARCHER applying to be a PROVIDER |
| voucher_id | uuid NOT NULL FK people | must be SEARCHER or above and not revoked when the vouch is given (trigger); CHECK (voucher_id <> applicant_id) |
| created_at | timestamptz NOT NULL | |
| withdrawn_at | timestamptz | can be set until the applicant is admitted |

UNIQUE (applicant_id, voucher_id). A vouch is *live* when it is not withdrawn and its voucher is not revoked; that is computed when reading, not stored.

### vouch_links and group_invitations
| Table | Columns |
|---|---|
| vouch_links | id, person_id FK (the applicant), token_hash text UNIQUE, expires_at, revoked_at, created_at |
| group_invitations | id, home_group_id FK, created_by_id FK people, token_hash text UNIQUE, expires_at, revoked_at, created_at |

Tokens are long random values; only the hash is stored (length, lifetime and limits: decision D-16).

### group_requests
id, requester_id FK people, church_id FK, group_name varchar(200), state text CHECK in (open, approved, declined), decided_by_id FK people null, decided_at null, created_at. At most one open request per requester (partial unique index).

### admin_invitations
id, email text, church_name varchar(200), invited_by_id FK people (the OWNER), token_hash UNIQUE, expires_at, accepted_at null, created_at. The church is created when the invitation is accepted, so it never exists without an ADMIN. On acceptance the email is cleared.

### handover_requests
id, owner_id FK people, new_owner_id FK people (an ADMIN of another church), successor_admin_id FK people null, successor_leader_id FK people null, created_at, accepted_at null, cancelled_at null. At most one open request (partial unique index).

### move_requests
id, person_id FK people, from_group_id FK, to_group_id FK (same church, CHECK in the service), agreed_by_person_at, agreed_by_from_leader_at, agreed_by_to_leader_at (each null until given), created_at, completed_at null, cancelled_at null. The move happens, in one transaction, when all three are set.

### notifications
id, person_id FK people, kind text, subject_id uuid null (the person or group the event is about), created_at, read_at null. No names or numbers are stored; clients load details through the normal endpoints. Index `(person_id, read_at, created_at)`. Retention is open detail O-02.

### contact_views
id, viewer_id FK people, person_id FK people, screen text, viewed_at. One row each time a verifier screen shows a mobile number (decision D-07). The number itself is never stored. Retention is open detail O-03.

### labels
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| label_name | text NOT NULL | |
| label_type | text NOT NULL | CHECK in (skill, language, timing, nativity, skill_level) |
| is_active | boolean NOT NULL default true | |
| | | UNIQUE (label_type, label_name) |

### person_labels
| Column | Type | Notes |
|---|---|---|
| person_id | uuid FK people | PK part |
| label_id | uuid FK labels | PK part |
| level_label_id | uuid FK labels, nullable | only for skill labels; must point to a `skill_level` label. Enforced by a database trigger and a CHECK that it differs from `label_id` |

### person_unavailability
id uuid PK, person_id FK, unavailable_from timestamptz, unavailable_to timestamptz, CHECK (unavailable_from < unavailable_to). An exclusion constraint (`btree_gist` extension) prevents overlapping periods for the same person; back-to-back periods are allowed.

### ratings
id uuid PK, rater_id FK people, provider_id FK people, rating smallint CHECK (rating BETWEEN 1 AND 10), comment text, rated_on timestamptz, updated_at timestamptz null (set when the rating is edited), UNIQUE (rater_id, provider_id) (Q5), CHECK (rater_id <> provider_id). Ratings stay when a person's account is closed; the rater is never shown to the provider.

### phone_reveals
id uuid PK, revealer_id FK people, provider_id FK people, revealed_at timestamptz, channel text CHECK (dial/show), source text CHECK (search/detail), searched_skills text[] null (at most 10). The number itself is never stored. Indexes: `(revealer_id, revealed_at)` for rate limiting, `provider_id`, `revealed_at`.

### login_history
id uuid PK, person_id uuid null, login_email text null, login_time timestamptz, succeeded boolean, ip_address inet null, user_agent text null. No foreign keys, so rows survive account closing; when the account is closed, `login_email`, `ip_address` and `user_agent` of that person's rows are set to NULL (the exception named in the conventions; the column is nullable since migration `0010`).

### password_reset_tokens
id uuid PK, person_id FK people, token_hash text, expires_at timestamptz, used_at timestamptz null.

### refresh_tokens
id uuid PK, person_id FK people, token_hash text, expires_at timestamptz, revoked_at timestamptz null, created_at timestamptz, replaced_by uuid null (rotation).

### report_schedules and report_runs
- `report_schedules`: id, report_name, cron_expression, timezone, is_enabled, recipients (text).
- `report_runs`: id, report_name, window_from, window_to, started_at, finished_at, status (running/succeeded/failed), file_path, row_count, error_message. UNIQUE (report_name, window_from, window_to) for idempotency.

## The six invariants as database constraints

Numbers are those of the [data model summary](../verification.md#data-model-summary). Everything that must hold only at the end of a transaction is declared deferrable and is checked at `COMMIT`: the foreign keys, the constraint triggers, and the "only one" rules, which are **exclusion constraints** (`EXCLUDE USING btree ... DEFERRABLE INITIALLY DEFERRED`, with the `btree_gist` extension already in use) because a partial unique index cannot be deferred. That is what lets a succession or handover change two rows in one transaction in any order.

| # | Rule | Enforced by |
|---|---|---|
| 1 | Exactly one OWNER | `EXCLUDE USING btree (status WITH =) WHERE (status = 'owner' AND closed_at IS NULL) DEFERRABLE INITIALLY DEFERRED` (at most one); a deferred constraint trigger fails the commit if no open OWNER exists |
| 2 | Every open, non-revoked person has a home group of their own church | `CHECK ((home_group_id IS NULL) = (status = 'revoked' OR closed_at IS NOT NULL))` and the composite foreign key `(home_group_id, church_id)` |
| 3 | Every open church has exactly one ADMIN | `EXCLUDE USING btree (church_id WITH =) WHERE (status = 'admin' AND closed_at IS NULL) DEFERRABLE INITIALLY DEFERRED`; deferred constraint trigger: `churches.admin_id` is that ADMIN, or the OWNER in the OWNER's own church (which then has no `admin` person) |
| 4 | Every open home group has exactly one leader, who belongs to it | the exclusion constraint on `home_groups.leader_id` above (open groups only); deferred constraint trigger: the leader has `status_rank >= 4`, is open, and has `home_group_id` equal to the group |
| 5 | Every VERIFIER leads their own group | Deferred constraint trigger on `people`: if `status = 'verifier'` then the group in `home_group_id` has this person as `leader_id` |
| 6 | A leader never stops leading without a successor in the same transaction | The deferred triggers of rules 3 and 4 fail the commit otherwise; closing a group or church sets `closed_at` in the same transaction, which exempts it |

The service layer decides who may do what (the permission module of S2.2); the constraints are the last line of defence and are tested one by one.

## Indexes

- `people`: unique indexes on `lower(email)` and on `mobile_number`, each `WHERE closed_at IS NULL` (immediate; a person's own email is not swapped within a transaction) (revoked accounts count as open, which stops a revoked person signing up again); `(church_id, status)`; `(home_group_id, status)`; `(last_home_group_id)`; partial index on providers for search `(status) WHERE status_rank(status) >= 3 AND closed_at IS NULL`; `created_at` (reports).
- `status_changes (person_id, at)`, `(changed_by_id)` (re-check flags and the chain of trust).
- `vouches (applicant_id)`, `(voucher_id)`.
- `labels (label_type, label_name)`; `person_labels (label_id)`; `ratings (provider_id)`; `phone_reveals (revealer_id, revealed_at)`, `(provider_id)`, `(revealed_at)`.
- `login_history (login_time)`, `(login_email, login_time)`.
- `person_unavailability (person_id, unavailable_from, unavailable_to)`.
- `notifications (person_id, read_at, created_at)`.
- Search at 10 000 people and 4 000 providers is measured in S5.2; indexes are adjusted then.

## Seed data (labels)

| Type | Values |
|---|---|
| skill | plumbing, electrical, networking, patientcare, assistance |
| timing | 06-12, 08-06, 20-24, 24h (meaning of 08-06: Q2) |
| language | English, Hindi, Tamil |
| nativity | Indian, Srilankan, Keralite, Bangla, Philippines |
| skill_level | basic, 50%, 80% |

Seeding is done by a migration so every environment has the same base labels. The report schedules are seeded in the same way (timezone Asia/Dubai); the set follows the redefined reports of S5.3. The first church, home group and OWNER are not seeded: the operator command `create-owner` (S2.4) creates them.
