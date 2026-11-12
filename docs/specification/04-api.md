# 04 REST API

Contract: OpenAPI 3 served at `/openapi.json` (docs at `/docs`) and committed as [`docs/openapi.json`](../openapi.json), which CI keeps equal to the code (`make openapi` rewrites it). The mobile app's tests read that file (`mobile/test/contract/`), so a change to an endpoint or field the app uses fails in the same pull request. Decision records: [ADR-0016](../adr/0016-church-trust-hierarchy-verification-model.md) (the model), [ADR-0017](../adr/0017-authorisation-by-status.md) (authorisation by status; it replaces ADR-0004).

This file is the **target** contract of the church trust model. `/api/v1` is changed in place (decision D-04); the code moves to it in slices S2 to S5. Resource paths for providers and searchers keep their names (`/freelancers/...`, `/search/freelancers`, `/workhosts/me/ratings`) for compatibility; who may call them changes from the old roles to the person's **status**.

## Conventions (must work for web and mobile)

- Base path `/api/v1`. JSON only. Never break v1 after the mobile app ships; add `/api/v2` instead.
- Auth: `Authorization: Bearer <access_token>`. No cookies, no redirects.
- Timestamps ISO 8601 UTC. Ids are UUID strings. Enums are plain strings. Statuses are `revoked`, `pending`, `searcher`, `provider`, `verifier`, `admin`, `owner`.
- Pagination: `?page=1&page_size=20` (max 100) returns `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`.
- Errors: `{ "error": { "code": "string", "message": "string", "details": {} } }` with proper HTTP status (400, 401, 403, 404, 409, 422, 429).
- CORS origins configured by environment variable.
- Rate limiting on auth and link endpoints; `429` with `Retry-After`.

## Transition (until the cut-over)

While the older accounts still exist (decision D-20), `POST /auth/login` and `POST /auth/forgot-password` accept an optional `user_type`. Without it, or with `person`, they use the one identity of the church trust model; with `freelancer`, `workhost`, `organisation` or `admin` they use the older accounts. Tokens of a person carry no role or status, and every request reads the person from the database (`403 account_revoked` for a revoked person on every endpoint but the few that allow it, `401` for a closed account). The field is removed with the last older account type (S5.2). `GET /me` answers a person with `PersonMeResponse` (the shape below) and an older account with the older `MeResponse` until the older accounts are gone; a revoked person can still read it. `PUT /me` is for people only.

## Authorisation by status

- The access token identifies the person only. On **every** request the server loads the person (status, closed flag, church, home group) and decides with the permission module (`inScope`, `canSetStatus`, `canAdmit`, ADR-0017). A status change therefore takes effect on the next request. Clients learn the status from `GET /me`, never from the token.
- "**at least X**" below means that status or any higher one. Closed accounts and unknown tokens get `401`. A **revoked** person can still log in (correct password) but every endpoint except `/me`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password` and `/app/config` answers `403 account_revoked`, so they keep their session and can see why they have no access. A **pending** applicant may call only `/me`, `/me/application`, `/me/vouch-link`, `/me/notifications`, `/churches` and `/churches/{id}/home-groups` (which are public anyway), the auth endpoints and `/app/config`; everything else is `403 not_admitted`.
- The scope of a verifier: a VERIFIER acts on people of their own home group (and people revoked from it), an ADMIN on their church, the OWNER on everyone. Out of scope is `404 not_found` for a person who exists, so existence is not revealed.
- A request that breaks a rule of the model (for example setting a status the actor may not set, or ending leadership without a successor) is `409` with a specific code, listed at the end.

### App configuration
| Method | Path | Notes |
|---|---|---|
| GET | /app/config | Public (no login). `{"terminology": {"profile", "terms": {...}}, "app": {"min_version", "latest_version"}}`. `terms` holds the words and address slugs of the active profile (`TERMINOLOGY_PROFILE`; an unknown name gives `default`), the same keys as `frontend/src/terminology/profiles.json`; a test fails when the two files differ. Versions are `X.Y.Z` from `APP_MIN_VERSION` and `APP_LATEST_VERSION` (default `0.0.0`, so nothing is blocked); the minimum must not be higher than the latest, otherwise the API refuses to start. `Cache-Control: public, max-age=300`. API paths never change with the words. Old apps are never rejected by the API; the app reads `min_version` and shows an update screen. |

### Test builds of the mobile app
| Method | Path | Notes |
|---|---|---|
| GET | /app/downloads | Any logged-in person who is not revoked. `{"items": [...]}`, newest first by version number; each item has `platform`, `version`, `build`, `released_at`, `size_bytes`, `sha256`, `notes`, `filename`. Empty when `DOWNLOADS_DIR` is not set. `Cache-Control: private, no-store`. |
| GET | /app/downloads/android/{version} | Any logged-in person who is not revoked. The APK (`application/vnd.android.package-archive`, attachment). `{version}` is `X.Y.Z` (digits only). **Errors:** `401` for a missing, malformed or expired token (checked first); `404 not_found` for every other failure alike, without saying which: a version that is not `X.Y.Z`, a version that is not in `index.json`, a listed file that is missing, and a path that would leave the downloads folder; `429 download_limit_reached` with `Retry-After` after `DOWNLOAD_MAX_PER_HOUR` downloads per person per hour (counted per API process, see the operations runbook). The token travels in the `Authorization` header, never in the address. |

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | /auth/signup | Public, rate limited per IP (`SIGNUP_MAX_PER_HOUR`, default 10 per hour). `full_name`, `email`, `mobile_number`, `password`, `requested_status` (`searcher` or `provider`), and either `home_group_id` or `invitation_token` (a group invitation link, which selects the church and group). Creates a PENDING person in that group, writes the `signup` history row and notifies its leader. `422 invalid_choice` for a group or link that is closed, unknown, expired or revoked (always the same answer). `409 account_exists` when an open account (revoked ones included) already has the email or the mobile number; one code for both, so the answer does not say which identifier matched or whose it is. Rate limited per IP. |
| POST | /auth/login | body: `email`, `password`. One login for everyone. Returns access and refresh tokens |
| POST | /auth/refresh | rotates refresh token |
| POST | /auth/logout | revokes refresh token |
| POST | /auth/forgot-password | always 202, never reveals whether email exists |
| POST | /auth/reset-password | token + new password |
| GET | /admin-invitations/{token} | Public. Shows the church name and invited email domain only. Rate limited. |
| POST | /admin-invitations/{token}/accept | Public. `full_name`, `mobile_number`, `password`, `home_group_name`. Creates the church, the home group and the person as its ADMIN and leader, in one transaction. |

Auth behaviour:

- Wrong password and unknown email give the same `401 invalid_credentials`.
- Throttling: after `LOGIN_MAX_FAILURES` failures within `LOGIN_WINDOW_MINUTES` for the same email and IP, login answers `429` with `Retry-After`. A successful login resets the count.
- Access token: JWT (HS256, signed with `JWT_SECRET`), `ACCESS_TOKEN_MINUTES`, subject is the person id, no role or status. Refresh token: opaque, stored hashed, `REFRESH_TOKEN_DAYS`, rotated on every use. Using a token that was already rotated or logged out revokes all sessions of that person.
- Password reset: the link (`FRONTEND_BASE_URL/reset-password?token=...`) is written to the server log until email delivery exists (open question Q7). Using it ends all sessions.
- Behind a reverse proxy the throttle sees the proxy address; start uvicorn with proxy headers.

### Me
| Method | Path | Notes |
|---|---|---|
| GET | /me | `user_type` (`person`, which tells this answer from the older one), `id`, `full_name`, `email`, `mobile_number`, `status`, `requested_status`, church and home group (`id`, `name`), `leader` of the home group (name), `status_set_by` (name), `flagged_for_recheck`, `vouch_count` |
| PUT | /me | `full_name`, `mobile_number` (the same uniqueness as sign-up; `409 account_exists` otherwise). A field left out keeps its value; an explicit null is refused. Not for a revoked person. |
| DELETE | /me | Closes the account (the stores' "delete account"). Body: `password` (`403 invalid_password` if wrong; wrong passwords are counted and throttled like login, `429` with `Retry-After`). Keeps the row, the history and the vouches given (they stop counting), clears the personal fields, ends every session, reset link and vouch link, and clears the address, network address and browser of the login attempts. A person who leads gets `409 leads_a_group` (VERIFIER) or `409 leads_a_church` (ADMIN, OWNER) until succession or handover is done (S4); a revoked person cannot close their account (`403 account_revoked`). |
| PUT | /me/application | PENDING only (`409 not_pending` otherwise, also when a leader admits the person at the same moment); an invalid group is `422 invalid_choice` and changes nothing. `home_group_id` and/or `requested_status`; the newly chosen leader is notified, vouches received still count. |
| POST | /me/apply-provider | SEARCHER only. Sets `requested_status` to `provider` and returns the vouch link. |
| GET | /me/vouch-link | PENDING, or a SEARCHER who applies to provide. `{"token": "...", "expires_at": "..."}`; the person shares the link `FRONTEND_BASE_URL/vouch/<token>`. |
| POST | /me/vouch-link/rotate | New token; the old one stops working. |
| GET | /me/vouches | Vouches received, with each voucher's name, church, whether it is live, and when. |
| GET | /me/vouches-given | Vouches given by the caller, with the applicant's name and status. |
| GET | /me/notifications | Paginated, newest first: `id`, `kind`, `subject` (id and name, loaded fresh), `created_at`, `read`. |
| POST | /me/notifications/{id}/read, /me/notifications/read-all | |

### Churches and home groups
| Method | Path | Notes |
|---|---|---|
| GET | /churches | **Public** (the sign-up screen has no token), rate limited per IP. Open churches by name: `id`, `name`; at most 500 (the number is small and set by the operators). No contact details. |
| GET | /churches/{id}/home-groups | Public, rate limited per IP like the one above. Open groups: `id`, `name`, `leader_name` (a name is needed to choose a group; no other detail about the leader). Leader names are shown to anonymous callers on purpose (decision D-19). |
| POST | /group-invitations/lookup | Public; the token is in the body, not the address, so it never reaches an access log of the API. Rate limited per IP (`LINK_LOOKUP_MAX_PER_HOUR`, default 30 per hour). Church name, group name and the leader's name for the sign-up screen. `404` for anything wrong, alike. |

### Vouching
| Method | Path | Notes |
|---|---|---|
| GET | /vouch-links/{token} | At least SEARCHER. The applicant's name, church, home group and what they apply for. `404` for anything wrong, alike. |
| POST | /vouch-links/{token}/vouch | At least SEARCHER. Creates the vouch. `409 already_vouched`; `403 cannot_vouch_self`. |
| DELETE | /vouches/{id} | The voucher, until the applicant is admitted. |

### Verifier (at least VERIFIER, within scope)
| Method | Path | Notes |
|---|---|---|
| GET | /verifier/applicants | PENDING applicants in scope, most-vouched first, each with `requested_status`, live vouch count and the vouchers. |
| GET | /verifier/members | People in scope that are admitted. Filter `status`, `home_group_id`. |
| GET | /verifier/revoked | The revoked list for the scope. |
| GET | /verifier/flagged | People flagged for re-checking, in scope. |
| GET | /verifier/people/{id} | One person in scope with their status history and chain of trust. Includes `mobile_number`; each call writes a `contact_views` row (decision D-07). This is the only response outside the reveal endpoint that contains a number. |
| POST | /verifier/people/{id}/admit | `to` (`searcher` or `provider`). Needs the vouches the role needs (`canAdmit`), else `409 not_enough_vouches`. |
| POST | /verifier/people/{id}/decline | Closes the application; nobody is revoked. |
| PUT | /verifier/people/{id}/status | `to` and, for reinstating, `home_group_id`. Within what the actor may set. Revoking appoints a successor in the same call when the person leads (`successor_id`). |
| POST | /verifier/people/{id}/reconfirm | Clears the re-check flag. |
| POST | /verifier/people/{id}/move | ADMIN or OWNER. `home_group_id`, same church. |
| POST, GET, DELETE | /verifier/group-invitations | Create, list and revoke invitation links to the home group the caller **leads** (`409 no_home_group` for an ADMIN or the OWNER who has handed their group on). The token (256 bits, url-safe) is returned once at creation and stored only as a hash; a link lives `INVITATION_LINK_DAYS` days (default 30). The list shows links that still work, without tokens. |

### Church structure and life cycle
| Method | Path | Notes |
|---|---|---|
| POST | /group-requests | At least SEARCHER. `group_name`. ADMIN or OWNER start a group at once (response `201` with the group). |
| GET | /group-requests | ADMIN or OWNER: open requests in scope. The requester: their own. |
| POST | /group-requests/{id}/approve, /decline | ADMIN or OWNER. Approval creates the group, moves the requester in as leader, and needs `successor_id` when the requester led a group. |
| POST | /move-requests | An admitted member who does not lead a group: `home_group_id`. |
| GET | /move-requests | Those that concern the caller (as mover or as leader). |
| POST | /move-requests/{id}/agree, /cancel | The mover or either leader. The move happens in the same transaction as the last agreement. |
| PUT | /home-groups/{id}/leader | ADMIN or OWNER. `successor_id` (a member of the group), `former_leader_status` (`provider` or `searcher`; or `keep` for ADMIN and OWNER handing on). |
| POST | /home-groups/{id}/close | The leader, who is the last member: `move_to_group_id`. Closes the group and moves the leader in one transaction. |
| PUT | /churches/{id}/admin | OWNER. `successor_id` (a member of the church), `former_admin_status`. |
| POST | /owner/churches | OWNER. `church_name`, `email`: creates an admin invitation. |
| GET, DELETE | /owner/churches/invitations | OWNER. List, cancel. |
| GET | /owner/churches | OWNER. All churches with counts. |
| POST | /owner/churches/{id}/close | OWNER; not their own church. |
| POST | /owner/handover | OWNER. `new_owner_id`, `successor_admin_id`, `successor_leader_id`. Creates the request. |
| GET | /owner/handover | The outgoing OWNER and the chosen ADMIN see the open request. |
| POST | /owner/handover/{id}/accept, /cancel | The chosen ADMIN accepts (everything happens in one transaction); either side cancels. |

The platform operators' OWNER change is a command run on the server, not an endpoint (see the operations runbook).

### Providers (resource paths kept)
| Method | Path | Who |
|---|---|---|
| GET, PUT | /freelancers/me | at least PROVIDER |
| PUT | /freelancers/me/labels | at least PROVIDER (replaces label set, with skill levels) |
| GET, POST | /freelancers/me/unavailability | at least PROVIDER |
| PUT, DELETE | /freelancers/me/unavailability/{id} | at least PROVIDER |
| GET | /freelancers/{id} | at least SEARCHER. The public profile of a PROVIDER or above who is open and not revoked; `404` otherwise. |
| GET | /freelancers/{id}/ratings | at least SEARCHER |

Behaviour of the core APIs:

- `GET /workhosts/me/ratings` (ratings given by the caller, at least SEARCHER) and the rating endpoints return `provider_name` with each rating. `GET /freelancers/{id}` returns `my_rating` (the caller's own rating of that provider, with its `id` for `PUT /ratings/{id}`), and `null` for everyone else. It also returns the provider's `church` and `home_group` (names) instead of vouching organisations.
- `PUT /freelancers/me` takes an optional `full_name`; leaving it out keeps the current name. Name changes are also possible through `PUT /me`.
- `PUT /freelancers/me/labels` replaces the whole label set. A skill may carry a `level_label_id` (a `skill_level` label); languages, timings and nativity take no level. Inactive labels cannot be selected.
- Unavailability periods need timezone-aware timestamps and cannot overlap (`409 unavailability_overlaps`).
- Public profile never contains the email or the mobile number.
- `POST /freelancers/{id}/reveal-mobile` (at least SEARCHER) is the only endpoint a searcher can use to get a provider's mobile number. Body: `channel` (`dial` or `show`), `source` (`search` or `detail`), `searched_skills` (at most 10 names, optional). Returns `{"mobile_number": "..."}` with `Cache-Control: no-store`, and records the reveal. Lower statuses get `403`, an unknown provider `404`. After `REVEAL_MAX_PER_HOUR` reveals in an hour or `REVEAL_MAX_PER_DAY` in 24 hours the caller gets `429 reveal_limit_reached` with `Retry-After`; nothing is recorded for a refused request. The verifier endpoint above is the one other place a number is returned.
- Ratings: one per rater and provider (`409 already_rated`; change it with `PUT /ratings/{id}`); nobody rates themselves. The ratings list does not show who rated.

### Labels
GET `/labels?type=skill|language|timing|nativity|skill_level` (at least SEARCHER). OWNER: POST `/labels`, PATCH `/labels/{id}`.

### Search
GET `/search/freelancers` (at least SEARCHER) with query parameters: `skill` (repeatable), `skill_match=any|all`, `skill_level`, `language`, `timing`, `nativity`, `max_rate`, `currency`, `negotiable`, `available_from`, `available_to`, `church_id`, `home_group_id`, `min_rating`, `sort=rating|rate|newest`, `page`, `page_size`.

Search behaviour: only open, non-revoked people of status PROVIDER or above who have at least one skill are listed, in every church; a rate and ratings are not needed (newcomers appear too). `max_rate` and `negotiable` only match providers who have a rate; `sort=rate` puts those without a rate last. `skill`, `language`, `timing` and `nativity` can be repeated and match case-insensitively by label name. `skill_match=any` (default) or `all`. `skill_level` applies to the chosen skills (or to any skill when none is given). `max_rate` needs `currency`. `available_from` and `available_to` must be given together and exclude providers with an overlapping unavailability period. `min_rating` excludes unrated providers. Default sort is `newest`. Results never contain email or mobile number (use the reveal endpoint).

### Ratings
POST `/ratings` (at least SEARCHER), PUT `/ratings/{id}` (own rating).

### Reports (OWNER and ADMIN; the set is redefined in [05](05-reports.md))
| Method | Path | Notes |
|---|---|---|
| GET | /reports | list the reports you may run (an ADMIN: those limited to their church) |
| GET | /reports/{name}?from=&to=&format=json\|csv | run on demand, nothing stored; an ADMIN's data is always limited to their church |
| GET | /reports/runs | run history, paginated (OWNER) |
| POST | /reports/{name}/run | run for a window and keep the files; body `{"date_from", "date_to"}`; `201` when it ran, `200` when it had already run (OWNER) |
| GET | /reports/runs/{id}/download?format=csv\|html | file download (OWNER) |
| GET | /reports/schedules | list schedules (OWNER) |
| PUT | /reports/schedules/{report} | change cron expression, time zone, enabled (OWNER) |

## Removed from the older contract

`POST /auth/register/freelancer|workhost|organisation`, the `user_type` field of login, `/admin/organisations*`, `/organisations*`, `/freelancers/me/vouches*`, `/workhosts/me` and the `org_id` and `vouch_count` search parameters. The app and web stop using them in slices S2 to S5; old app builds are forced to update at the cut-over (S6).

## Error codes added by the model

`account_exists`, `invalid_password`, `invalid_choice`, `not_pending`, `no_home_group`, `account_revoked`, `not_admitted`, `already_vouched`, `cannot_vouch_self`, `not_enough_vouches`, `not_in_scope` (reported as `not_found`), `status_not_allowed`, `leads_a_group`, `leads_a_church`, `successor_required`, `successor_not_member`, `group_not_empty`, `move_not_agreed`, `handover_open`.

## Authorisation rules (summary)

- A person can read and write only their own `/me` resources.
- Statuses are checked on every request against the database (ADR-0017); a token carries none.
- Searchers can search, view providers, rate and reveal; they cannot edit providers.
- Verifiers act only within their scope; the model's limits on what each may set are enforced by `canSetStatus`, and every status change is written to the history.
- OWNER-only endpoints return 403 for every other status.
