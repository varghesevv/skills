# Android application: web parity

Status: created 2026-10-29 from `frontend/src/App.tsx`, `frontend/src/portals/*`, `frontend/src/api/*` and `backend/app/api/v1/*.py` on branch `feat/android-dev`. **Keep this file current in every PR** that adds, changes or drops an app screen or an endpoint. It is the definition of "the app has every web feature" ([plan](plan.md) section 5).

Status values: `not started`, `in progress`, `done`, `n/a` (no app screen, for example the OWNER), `backend` (needs an API PR first; the PR id is given), `replaced` (not used any more: the organisation screens are gone, see the note below). Test file is filled in when the screen exists.

Words: the app never hard-codes the role words. The web paths below use the terminology slugs (`/church`, `/searchers`, ...); the app uses its own routes and the same words from `GET /api/v1/app/config`.

## Screens by status (church trust model)

[`docs/verification.md`](../verification.md) (ADR-0016, accepted 2026-11-12) and [ADR-0017](../adr/0017-authorisation-by-status.md) replace the portals by one login and screens that depend on the person's **status**: PENDING (applicant), SEARCHER, PROVIDER, VERIFIER, ADMIN; the OWNER works on the web only (decision D-11). The table below is the plan for the app, rewritten on 2026-11-12 from [specification 06](../specification/06-frontend.md) and [04](../specification/04-api.md). The web and backend still have the older model until slices S2 to S5 of the [roadmap](../roadmap-verification-model.md) land on `model/verification`; the **Slice** column says when each row is built. Rows for screens built before the model changed keep their `done` status and are moved onto the new endpoints in the slice named. Status values for the new rows start at `not started`. Words come from `GET /app/config`; the app never writes "searcher", "provider", "church" or "home group" itself.

## 1. Screens

### Public and account

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Welcome (sign in, sign up) | `pages/Landing.tsx` | S2.8 | done on the older model; one entry for everyone after S2.8 | `test/features/auth/auth_flow_test.dart` |
| Log in (one screen for everyone) | `pages/Login.tsx` | S2.8 | done as a screen per kind of account; becomes one screen | `test/features/auth/auth_flow_test.dart` |
| Sign-up wizard: details, church, home group (with leader name), searcher or provider | `pages/Register.tsx` (redone) | S2.8 | not started (replaces the older register forms) | |
| Join through a group invitation link | new | S2.8 | not started | |
| Forgot password | `pages/ForgotPassword.tsx` | | done | `test/features/auth/auth_flow_test.dart` |
| Reset password | `pages/ResetPassword.tsx` | | n/a (v1: the link opens in the browser) | |
| Applicant home: status, leader, vouches received, my vouch link (share sheet), change choice, leave | new | S2.8 | not started | |
| Revoked notice with log out | new | S2.8 | not started | |
| Navigation by status (bottom bar and routes) | `App.tsx` | S2.8 | not started (built per user type today) | |
| Home / dashboard | `pages/Dashboard.tsx` | S2.8 | done on the older model | `test/features/home/session_test.dart` |
| Log out | `auth/AuthContext.tsx` | | done | `test/features/home/session_test.dart` |
| Notifications list (mark read) | new | S3.6 | not started | |
| Settings: about, privacy link, version, close account | new | S5.11, S4.10 | in progress: version and log out done | `test/features/home/session_test.dart` |
| Minimum-version / update-required screen | none on web | | done | `test/app/config_gate_test.dart` |
| "This build is not configured" screen | none on web | | done | `test/core/env_test.dart` |
| Downloads (update hint) | planned | S7.1 | not started | |
| Not found | `pages/NotFound.tsx` | | not started | |

### Provider screens (PROVIDER and above)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Profile and rate | `ProfilePage.tsx` | S5.7 | done on `/freelancers/me`, moved to the person endpoints | `test/features/freelancer/profile_test.dart` |
| Labels (skills with level, languages, timings, nativity) | `LabelsPage.tsx` | S5.7 | done | `test/features/freelancer/labels_test.dart` |
| Availability list with add, edit, delete | `AvailabilityPage.tsx` | S5.7 | done (month calendar is for larger screens, not built) | `test/features/freelancer/availability_test.dart` |
| Ratings received | `RatingsPage.tsx` | S5.7 | done | `test/features/freelancer/ratings_test.dart` |
| Who vouched for me | `/me/vouches` | S3.6 | not started (replaces the organisation vouches screen) | |

### Searcher screens (SEARCHER and above)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Search with filters, name search, sort, chips, paging | `SearchPage.tsx` | S5.8 | not started | |
| Provider detail (labels, rate, ratings, church and home group, availability, my rating, rate form) | `FreelancerDetailPage.tsx` | S5.9 | not started | |
| Reveal: greyed placeholder, Reveal, `tel:` (number only in memory) | `RevealMobile.tsx`, FR-M-05 to FR-M-07 | S5.9 | not started | |
| Ratings given (edit) | `GivenRatingsPage.tsx` | S5.10 | not started | |
| Profile (name, mobile) | `/me` | S5.10 | not started | |
| Vouch from a received link (shows who asks) | new | S3.6 | not started | |
| Share my vouch link; apply to become a provider | new | S3.9 | not started | |
| Start a home group (request); move requests that concern me | new | S4.10 | not started | |
| (new) Message a provider | none on web | S8 | backend B6 | |

### Verifier screens (VERIFIER and above, within scope)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Applicants with vouches (most-vouched first), admit, decline | new | S3.7 | not started | |
| Members; person view with status history (mobile number shown here only, each view logged) | new | S3.7 | not started | |
| Revoked list, revoke, reinstate; flagged people, re-confirm | new | S4.10 | not started | |
| Group invitation link (share) | new | S4.10 | not started | |
| Step down and succession | new | S4.10 | not started | |

### ADMIN screens (in the app and on the web)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Group requests: approve, decline | new | S4.10 | not started | |
| Appoint or replace a group leader; move members; the church's people and revoked list | new | S4.10 | not started | |
| Church reports (table; CSV via share sheet) | RP-01, RP-03, RP-05, RP-07, RP-09 | after S5 | not started | |

### OWNER (web only, no app screens)

| Web page | Status |
|---|---|
| Churches, invitations, replace a church's ADMIN, labels, all reports, report history, schedules, handover | n/a |

### Cross-cutting behaviour to match

| Behaviour | Web source | Status |
|---|---|---|
| Error codes -> messages (`errorMessage`) incl. `invalid_credentials`, `too_many_attempts`; new codes of the model (`account_exists`, `account_revoked`, `not_admitted`, `not_enough_vouches`, ...) | `shared/errors.ts` | in progress: older codes done in `core/errors/error_messages.dart`; the new codes come with S2.8 |
| Validation rules and tests ported | `shared/validation.ts` | in progress: login, forgot password, provider profile and rate (`core/validation`); the sign-up wizard and other forms with their slices |
| Date / timezone handling (aware timestamps, local input) | `shared/dates.ts` | not started |
| Silent refresh on `401`, logout on refresh failure | `api/http.ts` | done (`core/api/api_client.dart`) |
| Status read from `GET /me` on start and after every `403` | `auth/AuthContext.tsx` | not started (S2.8) |
| Terminology tokens and profiles | `terminology/terms.ts` | done; the new keys (searcher, provider, verifier, admin, owner, church, home group) arrive in S2.9 |
| Loading, empty and error states on every list | spec 06 | not started |
| Accessibility: 48 dp targets, labels, 2.0 text scale, dark mode | plan section 1 | not started (S5.12) |

### Known differences from the web (on purpose)

| Topic | Web | App | Why |
|---|---|---|---|
| Error texts that mention the page (`not_found`, `already_rated`, label errors) | "Reload the page ..." | "Go back and try again." / "Open your rating to change it." | An app has no page to reload. |
| Reset-password link | opens `/reset-password` | opens in the browser (version 1) | The link is an address on the web site. |
| OWNER screens | web | none | Rare, administrative tasks (D-11). |

## 2. API endpoints used (`/api/v1`, target contract in [specification 04](../specification/04-api.md))

Status column: "at least X" means that status or higher.

| Method and path | Who | App use | Slice | Status |
|---|---|---|---|---|
| POST `/auth/signup` | public | Sign-up wizard | S2.8 | not started |
| POST `/auth/login`, `/auth/refresh`, `/auth/logout` | public / any | Login, refresh, logout | S2.8 | done on the older request shape (`user_type` is dropped in S2.8) |
| POST `/auth/forgot-password` | public | Forgot password | | done |
| POST `/auth/reset-password` | public | browser in v1 | | n/a (v1) |
| GET `/churches`, GET `/churches/{id}/home-groups`, GET `/group-invitations/{token}` | public | Sign-up wizard, join link | S2.8 | not started |
| GET, PUT, DELETE `/me`; PUT `/me/application`; POST `/me/apply-provider` | any, PENDING, SEARCHER | Session, applicant home, close account | S2.8, S4.10 | GET `/me` done on the older shape |
| GET, POST `/me/vouch-link`, `/me/vouch-link/rotate`; GET `/me/vouches`, `/me/vouches-given` | PENDING, SEARCHER, any admitted | Share link, who vouched | S3.6 | not started |
| GET `/me/notifications`; POST `.../{id}/read`, `/read-all` | any | Notifications | S3.6 | not started |
| GET `/vouch-links/{token}`; POST `/vouch-links/{token}/vouch`; DELETE `/vouches/{id}` | at least SEARCHER | Vouch from a link | S3.6 | not started |
| GET `/verifier/applicants`, `/members`, `/revoked`, `/flagged`, `/people/{id}` | at least VERIFIER | Verifier screens | S3.7, S4.10 | not started |
| POST `/verifier/people/{id}/admit`, `/decline`, `/reconfirm`, `/move`; PUT `.../status` | at least VERIFIER | Verifier screens | S3.7, S4.10 | not started |
| POST, GET, DELETE `/verifier/group-invitations` | at least VERIFIER | Share group link | S4.10 | not started |
| POST, GET `/group-requests`; POST `.../{id}/approve`, `/decline` | at least SEARCHER / ADMIN | Start a group, approve | S4.10 | not started |
| POST, GET `/move-requests`; POST `.../{id}/agree`, `/cancel` | admitted | Moves | S4.10 | not started |
| PUT `/home-groups/{id}/leader`; POST `/home-groups/{id}/close`; PUT `/churches/{id}/admin` | ADMIN, leader, OWNER | Succession | S4.10 | not started |
| GET, PUT `/freelancers/me`; PUT `/freelancers/me/labels`; unavailability endpoints | at least PROVIDER | Provider screens | S5.7 | done on the older rules (role -> status) |
| GET `/labels?type=` | at least SEARCHER | Labels, filter sheet | S5.7, S5.8 | in progress: labels screen done |
| GET `/freelancers/{id}`; GET `/freelancers/{id}/ratings` | at least SEARCHER | Detail, ratings | S5.9 | ratings received done; detail not started |
| POST `/freelancers/{id}/reveal-mobile` | at least SEARCHER | Reveal (dial). The number is never logged, sent to crash or analytics tools, or written to disk or cache; rules: [spec 07](../specification/07-non-functional.md), [ADR-0011](../adr/0011-secrets-from-environment-only.md), [plan](plan.md) sections 4 and 6 | S5.9 | not started |
| GET `/workhosts/me/ratings`; POST `/ratings`; PUT `/ratings/{id}` | at least SEARCHER | Ratings given, rate | S5.9, S5.10 | not started |
| GET `/search/freelancers` | at least SEARCHER | Search | S5.8 | not started |
| GET `/reports`, `/reports/{name}` | ADMIN (church) | Church reports | after S5 | not started |
| Reports runs, schedules, run; labels management; owner endpoints; handover; admin invitations | OWNER | none | | n/a |
| GET `/health` | public | release smoke test | | not started |

Removed from the app's use by the model: `/auth/register/*`, `user_type` in login, `/freelancers/me/vouches*`, `/organisations*`, `/admin/organisations*`, `/workhosts/me`.

## 3. New endpoints the app needs (separate backend PRs, so the web can use them too)

Ids follow [plan](plan.md) section 3 and are listed in order. The reveal endpoint already exists on `main`, so it is a normal row in section 2.

| Id | Endpoint | Why | Status |
|---|---|---|---|
| B1 | GET `/app/config` (public): terminology words and slugs, minimum and latest app version | role words; update check | done (merged, PR #79) |
| B2 | none: the app sends `X-App-Version` and `X-App-Platform`; the API never rejects old apps by header, the app reads `min_version` from B1 | minimum-version check | no server code needed |
| B3 | DELETE `/me` with password confirmation | store requirement | not started |
| B4 | GET `/app/downloads`, GET `/app/downloads/android/{version}`; `scripts/add-download.py` publishes a build | test builds behind login | API done (web Downloads page and the publish step of `mobile-release` still to do) |
| B5 | POST `/devices`, DELETE `/devices/{id}`, outbox, FCM sender | push | not started |
| B6 | `/chat/*` REST, `/chat/ws`, moderation, RP-10, RP-11 | chat | not started |
| B7 | `docs/openapi.json` exported and checked in CI (`make openapi`); app contract test `mobile/test/contract/api_contract_test.dart` | drift check. Generated Dart models are not part of B7 (see decision in the PR) | done |
