# Android application: web parity

Status: created 2026-10-29 from `frontend/src/App.tsx`, `frontend/src/portals/*`, `frontend/src/api/*` and `backend/app/api/v1/*.py` on branch `feat/android-dev`. **Keep this file current in every PR** that adds, changes or drops an app screen or an endpoint. It is the definition of "the app has every web feature" ([plan](plan.md) section 5).

Status values: `not started`, `in progress`, `done`, `n/a` (admin: no admin screens in the app), `backend` (needs an API PR first; the PR id is given). Test file is filled in when the screen exists.

Words: the app never hard-codes the role words. The web paths below use the terminology slugs (`/church`, `/searchers`, ...); the app uses its own routes and the same words from `GET /api/v1/app/config`.

## 1. Pages

### Public and account

| Web page (route) | Web source | App screen | Status | Test file |
|---|---|---|---|---|
| Landing (`/`) | `pages/Landing.tsx` | Welcome / role choice (sign in, register) | done | `test/features/auth/auth_flow_test.dart` |
| Log in, freelancer and work host (`/login`, `/login/<slug>`), with switch link | `pages/Login.tsx`, `pages/login/LoginForm.tsx` | Login screen per role | done (a screen per role; no switch link, the welcome screen offers each) | `test/features/auth/auth_flow_test.dart` |
| Organisation log in (`/login/organisation`), approval notice, link to sign-up | `pages/login/OrganisationLogin.tsx` | Login screen for organisation | done (approval notice, link to register) | `test/features/auth/auth_flow_test.dart` |
| Admin log in (`/login/admin`) | `pages/login/AdminLogin.tsx` | none: the app never sends `user_type=admin` | n/a | |
| Register choice (`/register`) | `pages/Register.tsx` | Register: choose role | done (the welcome screen) | `test/features/auth/auth_flow_test.dart` |
| Register freelancer / work host / organisation (`/register/:type`) | `pages/Register.tsx` | Register forms (same validation as `shared/validation.ts`) | done | `test/features/auth/auth_flow_test.dart` |
| Forgot password (`/forgot-password`) | `pages/ForgotPassword.tsx` | Forgot password (always shows the generic confirmation) | done | `test/features/auth/auth_flow_test.dart` |
| Reset password (`/reset-password?token=`) | `pages/ResetPassword.tsx` | v1: link opens in the browser; no app screen | n/a (v1) | |
| Not found | `pages/NotFound.tsx` | Unknown-route screen | not started | |
| Dashboard (account facts, shortcuts) | `pages/Dashboard.tsx` | Home / dashboard per role | done (account facts; shortcuts come with the features) | `test/features/home/session_test.dart`, `test/features/auth/auth_flow_test.dart` |
| Log out | `auth/AuthContext.tsx` | Settings: log out (revokes refresh token) | done | `test/features/home/session_test.dart` |
| Downloads page (login protected) | planned, `mobile-app-plan.md` 6.4 | Settings: version and "update available" hint | backend B4 | |
| (new) Minimum-version / update-required screen | none on web | Blocking screen | backend B1 | |
| (new) Settings: about, privacy link, version, delete account | none on web | Settings | backend B3 | |

### Freelancer portal

| Web page | Web source | App screen | Status | Test file |
|---|---|---|---|---|
| Profile and rate (name, mobile, WhatsApp, nationality, language, rate, currency, negotiable) | `portals/freelancer/ProfilePage.tsx` | Profile | not started | |
| Labels (skills with level, languages, timings, nativity) | `LabelsPage.tsx` | Labels editor | not started | |
| Unavailability (month calendar on tablet/desktop; list on phone) | `AvailabilityPage.tsx`, `MonthCalendar.tsx` | Availability list with add/edit/delete | not started | |
| My ratings (received, paged) | `RatingsPage.tsx` | Ratings received | not started | |
| My organisation vouches (accept / reject) | `VouchesPage.tsx` | Vouches | not started | |

### Work host portal

| Web page | Web source | App screen | Status | Test file |
|---|---|---|---|---|
| Search with filters, name search, sort, chips, paging | `SearchPage.tsx`, `FilterForm.tsx`, `searchParams.ts`, `activeFilters.ts` | Search + filter sheet | not started | |
| Freelancer detail (labels, rate, ratings, vouching organisations, availability, my rating, rate form) | `FreelancerDetailPage.tsx` | Detail | not started | |
| Mobile number on detail and result cards (greyed placeholder, Reveal, wait time on `429`) | `workhost/RevealMobile.tsx`, spec FR-W-06 to FR-W-08 | **Reveal** button: `POST /freelancers/{id}/reveal-mobile` with `channel=dial`, `source`, `searched_skills`, then `tel:`; number only in memory, cleared on leaving | not started | |
| Ratings given (edit) | `GivenRatingsPage.tsx` | Ratings given | not started | |
| Profile and available days | `HostProfilePage.tsx` | Profile | not started | |
| (new) Message a freelancer | none on web | Start chat | backend B6 | |

### Organisation portal

| Web page | Web source | App screen | Status | Test file |
|---|---|---|---|---|
| Vouched freelancers (status, revoke) | `organisation/VouchedPage.tsx` | Vouched list | not started | |
| Search (same page as work host, vouch from result/detail) | `SearchPage portal="organisation"` | Search | not started | |
| Freelancer detail (organisation view, vouch/revoke) | `FreelancerDetailPage portal="organisation"` | Detail | not started | |
| Organisation reports (`vouching_summary`, own data, table, CSV) | `organisation/ReportsPage.tsx` | Report screen (table; CSV via share sheet) | not started | |
| Profile | `OrgProfilePage.tsx` | Profile; pending-approval state | not started | |

### Admin portal (no admin screens in the app)

| Web page | Status |
|---|---|
| Organisation approvals (`AdminOrganisationsPage`), reports (`AdminReportsPage`), report history (`RunsPage`), schedules (`SchedulesPage`), labels (`AdminLabelsPage`) | n/a |

### Cross-cutting behaviour to match

| Behaviour | Web source | Status |
|---|---|---|
| Error codes -> messages (`errorMessage`) incl. `invalid_credentials`, `too_many_attempts` (minutes from `Retry-After`), `organisation_pending/rejected` | `shared/errors.ts` | not started |
| Validation rules and tests ported | `shared/validation.ts`, `validation.test.ts` | in progress: login, register, forgot password (`core/validation`, `test/core/validation/validators_test.dart`); profile rules in phase 2 |
| Date / timezone handling (aware timestamps, local input) | `shared/dates.ts` | not started |
| Silent refresh on `401`, logout on refresh failure | `api/http.ts` | not started |
| Terminology tokens and `church` profile | `terminology/terms.ts` | backend B1 |
| Loading, empty and error states on every list | spec 06 | not started |
| Accessibility: 48 dp targets, labels, 2.0 text scale, dark mode | plan section 1 | not started |

## 2. API endpoints used by the web (`/api/v1`)

Role column: F freelancer, W work host, O organisation, A admin, * any logged in.

| Method and path | Roles | Used by (web) | App use | Status |
|---|---|---|---|---|
| POST `/auth/register/freelancer` `/workhost` `/organisation` | public | Register | Register | done |
| POST `/auth/login` | public | Login | Login | done |
| POST `/auth/refresh` | public | `http.ts` | token refresh | not started |
| POST `/auth/logout` | * | logout | logout | done |
| POST `/auth/forgot-password` | public | ForgotPassword | Forgot password | done |
| POST `/auth/reset-password` | public | ResetPassword | browser in v1 | n/a (v1) |
| GET `/me` | * | AuthContext, Dashboard | session / dashboard | done |
| GET, PUT `/freelancers/me` | F | ProfilePage | Profile | not started |
| PUT `/freelancers/me/labels` | F | LabelsPage | Labels | not started |
| GET `/labels?type=` | * | Labels, filters | Labels, filter sheet | not started |
| GET, POST `/freelancers/me/unavailability`; PUT, DELETE `/freelancers/me/unavailability/{id}` | F | AvailabilityPage | Availability | not started |
| GET `/freelancers/me/vouches`; POST `.../vouches/{org_id}/accept\|reject` | F | VouchesPage | Vouches | not started |
| GET `/freelancers/{id}` | W, O, A | FreelancerDetailPage | Detail, as work host or organisation only (no admin screens). The response never contains email or mobile number; the number comes only from reveal-mobile | not started |
| GET `/freelancers/{id}/ratings` | * | RatingsPage, detail | Ratings | not started |
| POST `/freelancers/{id}/reveal-mobile` | W | `RevealMobile.tsx` | Reveal (dial). The number is never logged, sent to crash or analytics tools, or written to disk or cache; rules: [spec 07 Secrets and logging](../specification/07-non-functional.md), [ADR-0011](../adr/0011-secrets-from-environment-only.md), [plan](plan.md) sections 4 (phase 3) and 6 | not started |
| GET, PUT `/workhosts/me` | W | HostProfilePage | Profile | not started |
| GET `/workhosts/me/ratings` | W | GivenRatingsPage | Ratings given | not started |
| POST `/ratings`; PUT `/ratings/{id}` | W | detail, GivenRatingsPage | Rate | not started |
| GET `/organisations` | W, O, A | filter "vouched by" | Filter sheet | not started |
| GET, PUT `/organisations/me` | O | OrgProfilePage | Profile | not started |
| GET `/organisations/me/freelancers` | O | VouchedPage | Vouched list | not started |
| POST, DELETE `/organisations/me/freelancers/{freelancer_id}` | O | detail, VouchedPage | Vouch / revoke | not started |
| GET `/search/freelancers` (all filters incl. `name`) | W, O, A | SearchPage | Search, as work host or organisation only (no admin screens). Results never contain email or mobile number | not started |
| GET `/reports`; GET `/reports/{name}` (`vouching_summary`, json/csv) | O (the API also allows A) | organisation ReportsPage | Report screen for organisations only; the app has no admin access | not started |
| GET `/reports/runs`, `/reports/runs/{id}/download`, `/reports/schedules`; PUT `/reports/schedules/{report}`; POST `/reports/{name}/run` | A | admin pages | none | n/a |
| GET `/admin/organisations`; POST `/admin/organisations/{id}/approve\|reject` | A | admin pages | none | n/a |
| GET `/labels?include_inactive=true`; POST `/labels`; PATCH `/labels/{id}` | A | AdminLabelsPage | none | n/a |
| GET `/health` | public | ops | release smoke test | not started |

## 3. New endpoints the app needs (separate backend PRs, so the web can use them too)

Ids follow [plan](plan.md) section 3 and are listed in order. The reveal endpoint already exists on `main`, so it is a normal row in section 2.

| Id | Endpoint | Why | Status |
|---|---|---|---|
| B1 | GET `/app/config` (public): terminology words and slugs, minimum and latest app version | role words; update check | done (merged, PR #79) |
| B2 | none: the app sends `X-App-Version` and `X-App-Platform`; the API never rejects old apps by header, the app reads `min_version` from B1 | minimum-version check | no server code needed |
| B3 | DELETE `/me` with password confirmation | store requirement | not started |
| B4 | GET `/app/downloads`, GET `/app/downloads/android/{version}` | test builds behind login | not started |
| B5 | POST `/devices`, DELETE `/devices/{id}`, outbox, FCM sender | push | not started |
| B6 | `/chat/*` REST, `/chat/ws`, moderation, RP-09, RP-10 | chat | not started |
| B7 | `docs/openapi.json` exported and checked in CI | generated Dart models, drift check | not started |
