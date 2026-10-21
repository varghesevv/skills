# 04 REST API

Contract: OpenAPI 3 served at `/openapi.json` (docs at `/docs`). Decision record: [ADR-0004](../adr/0004-stateless-token-auth-for-web-and-mobile.md).

## Conventions (must work for web and mobile)

- Base path `/api/v1`. JSON only. Never break v1 after the mobile app ships; add `/api/v2` instead.
- Auth: `Authorization: Bearer <access_token>`. No cookies, no redirects.
- Timestamps ISO 8601 UTC. Ids are UUID strings. Enums are plain strings.
- Pagination: `?page=1&page_size=20` (max 100) returns `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`.
- Errors: `{ "error": { "code": "string", "message": "string", "details": {} } }` with proper HTTP status (400, 401, 403, 404, 409, 422, 429).
- CORS origins configured by environment variable.
- Rate limiting on auth endpoints; `429` with `Retry-After`.

## Endpoints

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | /auth/register/freelancer | |
| POST | /auth/register/workhost | |
| POST | /auth/register/organisation | |
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

### Work hosts
GET, PUT `/workhosts/me`; GET `/workhosts/me/ratings`.

### Organisations
GET, PUT `/organisations/me`; GET `/organisations/me/freelancers`; POST `/organisations/me/freelancers/{freelancer_id}` (vouch); DELETE same path (revoke).

### Labels
GET `/labels?type=skill|language|timing|nativity|skill_level` (any authenticated). Admin: POST `/labels`, PATCH `/labels/{id}`.

### Search
GET `/search/freelancers` with query parameters: `skill` (repeatable), `skill_match=any|all`, `skill_level`, `language`, `timing`, `nativity`, `max_rate`, `currency`, `negotiable`, `available_from`, `available_to`, `org_id`, `min_rating`, `sort=rating|rate|newest`, `page`, `page_size`.

### Ratings
POST `/ratings` (workhost), PUT `/ratings/{id}` (own rating).

### Reports (admin; organisations see scoped reports)
| Method | Path | Notes |
|---|---|---|
| GET | /reports | list available reports |
| GET | /reports/{name}?from=&to=&format=json\|csv | run on demand |
| GET | /reports/runs | scheduled-run history |
| POST | /reports/{name}/run | manual run (admin) |
| GET | /reports/runs/{id}/download | file download |

## Authorisation rules

- A user can read and write only their own `/me` resources.
- Work hosts can rate only; they cannot edit freelancers.
- Organisations can vouch and revoke only for their own links.
- Admin-only endpoints return 403 for other roles.
