# Android application: web parity

Status: created 2026-10-29 from `frontend/src/App.tsx`, `frontend/src/portals/*`, `frontend/src/api/*` and `backend/app/api/v1/*.py` on branch `feat/android-dev`. **Keep this file current in every PR** that adds, changes or drops an app screen or an endpoint. It is the definition of "the app has every web feature" ([plan](plan.md) section 5).

Status values: `not started`, `in progress`, `done`, `n/a` (no app screen, for example the OWNER), `backend` (needs an API PR first; the PR id is given), `replaced` (not used any more: the organisation screens are gone, see the note below). Test file is filled in when the screen exists.

Words: the app never hard-codes the role words. The web paths below use the terminology slugs (`/church`, `/searchers`, ...); the app uses its own routes and the same words from `GET /api/v1/app/config`.

## Screens by status (church trust model)

The per-church ADMIN and the VERIFIER use the app; only the OWNER is web only (decision D-11, [FR-O-06](../specification/02-functional-requirements.md)). This narrows the older rule that the platform administrator has no mobile access, because the platform administrator is now the OWNER. [`docs/verification.md`](../verification.md) does not say which channels each role uses, so the decision is recorded in the decision log and the specification, and in [understanding](understanding.md) A2.

[`docs/verification.md`](../verification.md) (ADR-0016, accepted 2026-11-12) and [ADR-0017](../adr/0017-authorisation-by-status.md) replace the portals by one login and screens that depend on the person's **status**: PENDING (applicant), SEARCHER, PROVIDER, VERIFIER, ADMIN; the OWNER works on the web only (decision D-11). The table below is the plan for the app, rewritten on 2026-11-12 from [specification 06](../specification/06-frontend.md) and [04](../specification/04-api.md). The web and backend still have the older model until slices S2 to S5 of the [roadmap](../roadmap-verification-model.md) land on `model/verification`; the **Slice** column says when each row is built. Rows for screens built before the model changed keep their `done` status and are moved onto the new endpoints in the slice named. Status values for the new rows start at `not started`. Words come from `GET /app/config`; the app never writes "searcher", "provider", "church" or "home group" itself.

## 1. Screens

### Public and account

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Welcome (sign in, sign up) | `pages/Landing.tsx` | S2.8 | done: a Join and Sign in card for people next to the older entries, which go with the older accounts (S5) | `test/features/person/person_flow_test.dart`, `test/features/auth/auth_flow_test.dart` |
| Log in (one screen for everyone) | `pages/person/PersonSignIn.tsx` | S2.8 | done for people at `/sign-in` (no account type sent); the older screens go with the older accounts (S5) | `test/features/person/person_flow_test.dart` |
| Sign-up wizard: details, church, home group (with leader name), searcher or provider | `pages/person/SignUp.tsx` | S2.8 | done at `/sign-up`; the older register forms go with the older accounts | `test/features/person/person_flow_test.dart` |
| Join through a group invitation link | `/join/<token>` | S2.8 | done: a link or token pasted on the sign-up screen opens `/join/<token>` (the token goes in a body, never in an address); opening a link from outside the app (app links) is later | `test/features/person/person_flow_test.dart` |
| Forgot password | `pages/ForgotPassword.tsx` | | done | `test/features/auth/auth_flow_test.dart` |
| Reset password | `pages/ResetPassword.tsx` | | n/a (v1: the link opens in the browser) | |
| Applicant home: status, leader, change choice, leave; vouches received and my vouch link | `pages/person/ApplicantHome.tsx` | S2.8, S3.6 | done; the link is made and copied (shown once); the phone's share sheet needs a plugin and comes with the release setup; change of group or status, and leaving with the password asked again | `test/features/person/person_home_test.dart`, `test/features/person/vouching_test.dart` |
| Revoked notice with log out | `pages/person/PersonHome.tsx` | S2.8 | done | `test/features/person/person_home_test.dart` |
| Navigation by status (bottom bar and routes) | `App.tsx` | S2.8, S3.6 | in progress: a person lives at `/member` and below it, and the router lets each status reach only its own pages (applicant: home and notifications; admitted: the member pages and the vouch page; revoked: home only); the older accounts keep their own tabs; tabs for admitted people come with S3 and S5 | `test/features/person/person_home_test.dart`, `test/features/person/vouching_test.dart` (the table of who may go where) |
| Home / dashboard | `pages/Dashboard.tsx` | S2.8 | done on the older model | `test/features/home/session_test.dart` |
| Log out | `auth/AuthContext.tsx` | | done | `test/features/home/session_test.dart` |
| Notifications list (mark read) | new | S3.6 | done: a bell with the unread count in the top bar, polled every minute, a list with mark one or all as read | `test/features/person/vouching_test.dart` |
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
| Who vouched for me | `/me/vouches` | S3.6 | done on the applicant home (no organisation vouches screen any more) | `test/features/person/vouching_test.dart` |

### Searcher screens (SEARCHER and above)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Search with filters, name search, sort, chips, paging | `SearchPage.tsx` | S5.8 | not started | |
| Provider detail (labels, rate, ratings, church and home group, availability, my rating, rate form) | `FreelancerDetailPage.tsx` | S5.9 | not started | |
| Reveal: greyed placeholder, Reveal, `tel:` (number only in memory) | `RevealMobile.tsx`, FR-M-05 to FR-M-07 | S5.9 | not started | |
| Ratings given (edit) | `GivenRatingsPage.tsx` | S5.10 | not started | |
| Profile (name, mobile) | `/me` | S5.10 | not started | |
| Vouch from a received link (shows who asks) | new | S3.6 | done: paste the link, see who asks, vouch; tapping a link in another app needs app links (release setup) | `test/features/person/vouching_test.dart` |
| Share my vouch link (S3.6); apply to become a provider (S3.9) | new | S3.6, S3.9 | done: a searcher asks to offer their skills, stays a searcher, and then has the same link and vouches as a new applicant | `test/features/person/vouching_test.dart`, `test/features/person/provider_upgrade_test.dart` |
| Start a home group (request); move requests that concern me | new | S4.10b | done: starting a home group (any admitted member asks and sees their own requests; an ADMIN or the OWNER start one at once, naming who leads their current group when they lead one), and moving to another group by agreement (the member asks, the leader of the group they leave or join agrees once, either leader or the member cancels; every move that concerns the person is listed with who agreed; a leader is told to hand their group on first) | `test/features/groups/group_requests_test.dart` |
| (new) Message a provider | none on web | S8 | backend B6 | |

### Verifier screens (VERIFIER and above, within scope)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Applicants with vouches (most-vouched first), admit, decline | `leader/Applicants.tsx` | S3.7 | done: each applicant with the vouchers (those that no longer count marked), admit as a searcher or a provider (the provider button is off unless the server says it will work), decline after asking; a searcher who asks to become a provider (the S3.9 backend, pull request 127) has only the provider admission, and decline ends just the request; paged (50) with pull to refresh | `test/features/leader/leader_test.dart` |
| Members; person view with status history. The mobile number is shown here only, one person at a time, each view logged without the number: the exception defined in [spec 07 Privacy of verifier views](../specification/07-non-functional.md) and decision D-17. Same handling as Reveal: held in memory only, never logged, cached, written to disk or sent to crash or analytics tools | `leader/Members.tsx`, `leader/PersonDetail.tsx` | S3.7 | done: members by name with who admitted them and the re-check flag, a filter by status, and one person's page with the number (tap to open the dialler), vouches, history and chain of trust; the answer is kept in the screen only and asked for once, because each ask is logged | `test/features/leader/leader_test.dart` |
| Revoked list, revoke, reinstate; flagged people, re-confirm | new | S4.10a | done: the leader menu has the revoked and the flagged lists (paged by 50, no numbers); on one person's page a leader revokes a searcher or provider after asking, reinstates a revoked person into an open group of their church as a searcher or a provider, and confirms a flagged status, the page updating itself from the server's answer; a leader is not revoked by someone who may not: the page says so (an ADMIN or the OWNER revoke a VERIFIER there with the successor of their group, S4.10c; an ADMIN is revoked only by the OWNER, on the web) | `test/features/leader/status_test.dart` |
| Group invitation link (share) | new | S4.10c-2 | done: a leader makes a link to the group they lead (shown once, with the token only in the link, and copied), sees the links that still work (made and expiry, no token) and ends one; a leader who handed their group on is told so | `test/features/groups/invitations_test.dart` |
| Step down and succession | new | S4.10c, S4.10d-1 | done: a leader stops leading when an ADMIN or the OWNER choose a successor (the groups screen), or, being the last member of their group, closes it from their own screen by joining another open group (it asks first; a VERIFIER chooses to become a provider or a searcher, an ADMIN or the OWNER keep their status; a message says what happened, and a former VERIFIER lands on the home as a member) | `test/features/leader/admin_test.dart`, `test/features/groups/my_group_test.dart` |

### ADMIN screens (in the app and on the web)

| Screen | Web counterpart | Slice | Status | Test file |
|---|---|---|---|---|
| Group requests: approve, decline | new | S4.10b | done: an ADMIN sees the waiting requests of the church (the OWNER those of every church) and approves or declines each; when the requester leads a group, the successor comes from that group's members (`requester_group`), required unless the requester is alone in it; a failed member list keeps Approve off with a retry | `test/features/groups/group_requests_test.dart` |
| Appoint or replace a group leader; move members; the church's people and revoked list | new | S4.10c | done: the ADMIN's menu has the groups of the church with their leaders, each with a way to choose who leads it from now on (from that group's members; the old leader becomes a provider or a searcher, or keeps their status as an ADMIN or the OWNER), and on a member's page a move to another group of the church; an ADMIN or the OWNER also revoke a VERIFIER there together with the successor of their group; the church's people and the revoked list are the Members and Revoked screens, which an ADMIN sees for the whole church | `test/features/leader/admin_test.dart` |
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
| POST `/auth/signup` | public | Sign-up wizard | S2.8 | done |
| POST `/auth/login`, `/auth/refresh`, `/auth/logout` | public / any | Login, refresh, logout | S2.8 | done on the older request shape (`user_type` is dropped in S2.8) |
| POST `/auth/forgot-password` | public | Forgot password | | done |
| POST `/auth/reset-password` | public | browser in v1 | | n/a (v1) |
| GET `/churches`, GET `/churches/{id}/home-groups`, POST `/group-invitations/lookup` | public | Sign-up wizard, join link | S2.8 | done |
| GET, PUT `/me`; PUT `/me/application` | any, PENDING | Session, applicant home | S2.8 | GET `/me` (both shapes) and `PUT /me/application` done; `PUT /me` (name, mobile) comes with the profile screen (S5.10) |
| DELETE `/me` | any | Close account | S2.8 (applicant), S4.10 (others) | done for the applicant home; the settings screen of admitted people later |
| POST `/me/apply-provider` | SEARCHER | Apply to provide | S3.9 | done (not yet run on a phone, S6.1); a notice for the leader (`provider_application`) and for the person when the leader declines (`provider_declined`) are in the notification list |
| GET `/me/vouch-link`, POST `/me/vouch-link` (makes a new link and ends the one before; there is no `rotate` any more, decision D-25); GET `/me/vouches`, `/me/vouches-given` | PENDING, SEARCHER, any admitted | Share link (shown once), who vouched | S3.6 | done |
| GET `/me/notifications`; POST `.../{id}/read`, `/read-all` | any except REVOKED | Notifications | S3.6 | done |
| POST `/vouch-links/lookup`, `/vouch-links/vouch` (token in the body); DELETE `/vouches/{id}` | at least SEARCHER | Vouch from a link, withdraw | S3.6 | done |
| GET `/verifier/applicants`, `/members`, `/people/{id}`; `/revoked`, `/flagged` | at least VERIFIER | Verifier screens | S3.7 (applicants, members, one person), S4.10a (revoked, flagged) | done |
| POST `/verifier/people/{id}/admit`, `/decline`; `/reconfirm`, `/move`; PUT `.../status` | at least VERIFIER | Verifier screens | S3.7 (admit, decline), S4.10a (reconfirm, revoke, reinstate), S4.10c (move, revoke a VERIFIER) | done |
| POST, GET, DELETE `/verifier/group-invitations` | at least VERIFIER | Share group link | S4.10c-2 | done |
| POST, GET `/group-requests`; POST `.../{id}/approve`, `/decline` | at least SEARCHER / ADMIN | Start a group, approve | S4.10b | done |
| POST, GET `/move-requests`; POST `.../{id}/agree`, `/cancel` | admitted | Moves | S4.10b | done |
| PUT `/home-groups/{id}/leader`; POST `/home-groups/{id}/close`; PUT `/churches/{id}/admin` | ADMIN, leader, OWNER | Succession | S4.10c (leader), S4.10d-1 (close; the OWNER's `/churches/{id}/admin` is web only, decision D-11) | done |
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
| B3 | DELETE `/me` with password confirmation: closes the account (the row stays with `closed_at`, personal details cleared, trust record kept; [FR-X-03](../specification/02-functional-requirements.md)); this is the store's "delete account" | store requirement | not started (S4.4 backend, S4.10 app) |
| B4 | GET `/app/downloads`, GET `/app/downloads/android/{version}`; `scripts/add-download.py` publishes a build | test builds behind login | API done (web Downloads page and the publish step of `mobile-release` still to do) |
| B5 | POST `/devices`, DELETE `/devices/{id}`, outbox, FCM sender | push | not started |
| B6 | `/chat/*` REST, `/chat/ws`, moderation, RP-10, RP-11 | chat | not started |
| B7 | `docs/openapi.json` exported and checked in CI (`make openapi`); app contract test `mobile/test/contract/api_contract_test.dart` | drift check. Generated Dart models are not part of B7 (see decision in the PR) | done |
