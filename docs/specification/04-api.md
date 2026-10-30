# 04 REST API

Contract: OpenAPI 3 served at `/openapi.json` (docs at `/docs`) and committed as [`docs/openapi.json`](../openapi.json), which CI keeps equal to the code (`make openapi` rewrites it). The mobile app's tests read that file (`mobile/test/contract/`), so a change to an endpoint or field the app uses fails in the same pull request. Decision record: [ADR-0004](../adr/0004-stateless-token-auth-for-web-and-mobile.md).

## Conventions (must work for web and mobile)

- Base path `/api/v1`. JSON only. Never break v1 after the mobile app ships; add `/api/v2` instead.
- Auth: `Authorization: Bearer <access_token>`. No cookies, no redirects.
- Timestamps ISO 8601 UTC. Ids are UUID strings. Enums are plain strings.
- Pagination: `?page=1&page_size=20` (max 100) returns `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`.
- Errors: `{ "error": { "code": "string", "message": "string", "details": {} } }` with proper HTTP status (400, 401, 403, 404, 409, 422, 429).
- CORS origins configured by environment variable.
- Rate limiting on auth endpoints; `429` with `Retry-After`.

## Endpoints

### App configuration
| Method | Path | Notes |
|---|---|---|
| GET | /app/config | Public (no login). `{"terminology": {"profile", "terms": {...}}, "app": {"min_version", "latest_version"}}`. `terms` holds the words and address slugs of the active profile (`TERMINOLOGY_PROFILE`; an unknown name gives `default`), the same keys as `frontend/src/terminology/profiles.json`; a test fails when the two files differ. Versions are `X.Y.Z` from `APP_MIN_VERSION` and `APP_LATEST_VERSION` (default `0.0.0`, so nothing is blocked); the minimum must not be higher than the latest, otherwise the API refuses to start. `Cache-Control: public, max-age=300`. Stored `user_type` values and API paths never change with the words. Old apps are never rejected by the API; the app reads `min_version` and shows an update screen. |

### Test builds of the mobile app
| Method | Path | Notes |
|---|---|---|
| GET | /app/downloads | Any logged-in role. `{"items": [...]}`, newest first by version number; each item has `platform`, `version`, `build`, `released_at`, `size_bytes`, `sha256`, `notes`, `filename`. Empty when `DOWNLOADS_DIR` is not set. `Cache-Control: private, no-store`. |
| GET | /app/downloads/android/{version} | Any logged-in role. The APK (`application/vnd.android.package-archive`, attachment). Only versions listed in `index.json` exist; anything else is `404`. At most `DOWNLOAD_MAX_PER_HOUR` per person per hour, then `429 download_limit_reached` with `Retry-After`. The token travels in the `Authorization` header, never in the address. |

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | /auth/register/freelancer | email, mobile_number, password, **full_name**; optional nationality, primary_language, whatsapp_availability |
| POST | /auth/register/workhost | email, mobile_number, password, **full_name** |
| POST | /auth/register/organisation | email, mobile_number, password, **org_name** (Organisation Name) |
| POST | /auth/login | body: email, password, user_type. Returns access and refresh tokens |
| POST | /auth/refresh | rotates refresh token |
| POST | /auth/logout | revokes refresh token |
| POST | /auth/forgot-password | always 202, never reveals whether email exists |
| POST | /auth/reset-password | token + new password |
| GET | /me | current user and role |
| GET | /admin/organisations?status=pending | admin only, paginated |
| POST | /admin/organisations/{id}/approve | admin only |
| POST | /admin/organisations/{id}/reject | admin only |

Auth behaviour:

- Wrong password and unknown email give the same `401 invalid_credentials`. Organisations that are not approved get `403 organisation_pending` or `organisation_rejected`, but only after the correct password.
- Throttling: after `LOGIN_MAX_FAILURES` failures within `LOGIN_WINDOW_MINUTES` for the same email, user type and IP, login answers `429` with `Retry-After`. A successful login resets the count.
- Access token: JWT (HS256, signed with `JWT_SECRET`), `ACCESS_TOKEN_MINUTES`. Refresh token: opaque, stored hashed, `REFRESH_TOKEN_DAYS`, rotated on every use. Using a token that was already rotated or logged out revokes all sessions of that user.
- Password reset: the link (`FRONTEND_BASE_URL/reset-password?token=...`) is written to the server log until email delivery exists (open question Q7). Using it ends all sessions.
- Behind a reverse proxy the throttle sees the proxy address; start uvicorn with proxy headers (phase 7b).

### Freelancers
| Method | Path | Role |
|---|---|---|
| GET, PUT | /freelancers/me | freelancer |
| PUT | /freelancers/me/labels | freelancer (replaces label set, with skill levels) |
| GET, POST | /freelancers/me/unavailability | freelancer |
| PUT, DELETE | /freelancers/me/unavailability/{id} | freelancer |
| GET | /freelancers/me/vouches | freelancer |
| POST | /freelancers/me/vouches/{org_id}/accept or /reject | freelancer (if Q6) |
| GET | /freelancers/{id} | workhost, organisation, admin (public profile) |
| GET | /freelancers/{id}/ratings | any authenticated |

Behaviour of the core APIs:

- `GET /workhosts/me/ratings` and the rating endpoints return `freelancer_name` with each rating. `GET /freelancers/{id}` returns `my_rating` (the calling work host's own rating of that freelancer, with its `id` for `PUT /ratings/{id}`), and `null` for everyone else.
- `PUT /freelancers/me` and `PUT /workhosts/me` take an optional `full_name`; leaving it out keeps the current name. `GET /me`, the own-profile endpoints, the freelancer detail page and search results return `full_name`.
- `PUT /freelancers/me/labels` replaces the whole label set. A skill may carry a `level_label_id` (a `skill_level` label); languages, timings and nativity take no level. Inactive labels cannot be selected.
- Unavailability periods need timezone-aware timestamps and cannot overlap (`409 unavailability_overlaps`).
- Vouching: an approved organisation creates a `pending` vouch; the freelancer accepts (`approved`) or rejects (`revoked`). Only approved and active vouches are shown on the public profile. Revoking sets the vouch inactive; vouching again starts over as `pending`.
- Public profile never contains the email or the mobile number, for any role.
- `POST /freelancers/{id}/reveal-mobile` (work host only) is the only endpoint that returns a freelancer's mobile number. Body: `channel` (`dial` or `show`), `source` (`search` or `detail`), `searched_skills` (at most 10 names, optional). Returns `{"mobile_number": "..."}` with `Cache-Control: no-store`, and records the reveal. Other roles get `403`, an unknown freelancer `404`. After `REVEAL_MAX_PER_HOUR` reveals in an hour or `REVEAL_MAX_PER_DAY` in 24 hours the work host gets `429 reveal_limit_reached` with `Retry-After`; nothing is recorded for a refused request.
- Ratings: one per work host and freelancer (`409 already_rated`; change it with `PUT /ratings/{id}`). The ratings list does not show who rated.

### Work hosts
GET, PUT `/workhosts/me`; GET `/workhosts/me/ratings`.

### Organisations
GET `/organisations`: approved organisations (`id`, `org_name`) by name, up to 500, for work hosts, organisations and admins. It is what the "vouched by" search filter (`org_id`) offers. No contact details.

GET, PUT `/organisations/me`; GET `/organisations/me/freelancers` (each item has the freelancer's `full_name`, so the list can be read without opening every profile); POST `/organisations/me/freelancers/{freelancer_id}` (vouch); DELETE same path (revoke).

### Labels
GET `/labels?type=skill|language|timing|nativity|skill_level` (any authenticated). Admin: POST `/labels`, PATCH `/labels/{id}`.

### Search
GET `/search/freelancers` with query parameters: `skill` (repeatable), `skill_match=any|all`, `skill_level`, `language`, `timing`, `nativity`, `max_rate`, `currency`, `negotiable`, `available_from`, `available_to`, `org_id`, `min_rating`, `sort=rating|rate|newest`, `page`, `page_size`.

Search behaviour: freelancers are listed once they have at least one skill; a rate and ratings are not needed (newcomers appear too). `max_rate` and `negotiable` only match freelancers who have a rate; `sort=rate` puts those without a rate last. `skill`, `language`, `timing` and `nativity` can be repeated and match case-insensitively by label name. `skill_match=any` (default) or `all`. `skill_level` applies to the chosen skills (or to any skill when none is given). `max_rate` needs `currency`. `available_from` and `available_to` must be given together and exclude freelancers with an overlapping unavailability period. `org_id` and `vouch_count` only count approved, active vouches. `min_rating` excludes unrated freelancers. Default sort is `newest`. Results never contain email or mobile number (use the reveal endpoint). Roles: work host, organisation, admin.

### Ratings
POST `/ratings` (workhost), PUT `/ratings/{id}` (own rating).

### Reports (admin; organisations see scoped reports)
| Method | Path | Notes |
|---|---|---|
| GET | /reports | list the reports you may run (organisations: only `vouching_summary`) |
| GET | /reports/{name}?from=&to=&format=json\|csv | run on demand, nothing stored (admin; organisations only `vouching_summary`, always limited to their own data) |
| GET | /reports/runs | run history, paginated (admin) |
| POST | /reports/{name}/run | run for a window and keep the files; body `{"date_from", "date_to"}`; `201` when it ran, `200` when it had already run (admin) |
| GET | /reports/runs/{id}/download?format=csv\|html | file download (admin) |
| GET | /reports/schedules | list schedules (admin) |
| PUT | /reports/schedules/{report} | change cron expression, time zone, enabled (admin) |

## Authorisation rules

- A user can read and write only their own `/me` resources.
- Work hosts can rate only; they cannot edit freelancers.
- Organisations can vouch and revoke only for their own links.
- Admin-only endpoints return 403 for other roles.
