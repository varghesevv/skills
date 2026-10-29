# Android application: plan

Status: draft. Read [understanding](understanding.md) first, then this plan, then [chat design](chat-design.md). The technical choices (Flutter, Riverpod, go_router, dio, secure storage, generated API models, test levels, CI and release pipeline) are in [mobile-app-plan.md](../mobile-app-plan.md) sections 3 to 7; this plan does not repeat them, it adds Android-specific work, the API additions, chat and the order of work.

## 1. Principles

1. **Parity first, chat second.** Phases 1 to 4 deliver what the web does. Chat (phases 5 and 6) comes after, but its backend can be built in parallel by a separate branch.
2. **One API.** If the app needs data the API does not give, extend the API in a separate PR with tests and spec changes, so the web benefits too. Never an app-only endpoint without a reason written in the PR.
3. **Small PRs.** One topic per PR (a screen group, an endpoint group). Backend PRs and `mobile/` PRs are separate. Each PR has tests, updated specs/runbook, a Conventional Commit title and a description file in `temp/`.
4. **No secrets in source, logs or screenshots.** Server addresses are build settings. Test passwords and tokens are generated per run.
5. **Words from the server.** All role words come from `GET /api/v1/app/config`; the app has no copy of `profiles.json`.
6. **Accessibility from the first screen.** Tap targets at least 48 dp, labels on every control, text scale up to 2.0 without overflow, dark mode.

## 2. Phase 0: development environment and decisions (about 1 week)

The new session runs on a machine reached with VS Code Remote-SSH. Android tooling decides what is possible there, so check it first and record the result in `docs/android/environment.md`.

| Check | Command | Needed for |
|---|---|---|
| CPU and OS | `uname -m`, `cat /etc/os-release` | x86_64 Linux is the easy case. ARM64 (for example a Raspberry Pi) cannot run the Android emulator and the Android SDK tools are fragile there. |
| Java | `java -version` (JDK 17 or 21) | Gradle |
| Flutter | `flutter doctor -v` | build, test |
| Android SDK | `$ANDROID_HOME`, `sdkmanager --list_installed` | build |
| Emulator | `ls /dev/kvm`, `emulator -version` | integration tests (needs KVM on x86_64) |
| A real phone | `adb devices` | manual testing |
| Disk and RAM | `df -h`, `free -h` | Gradle needs several GB and 4 GB RAM or more |

**Options for running the app while developing over Remote-SSH** (pick one in phase 0):

1. **Physical phone with wireless debugging on the same network as the remote host**, `adb pair` / `adb connect` from the remote host. Simple, real hardware, works from ARM64 too if the SDK platform tools run there.
2. **Phone attached to the local computer**, running `adb` there and forwarding it to the remote host (`ssh -R 5037:127.0.0.1:5037` with `adb -H` on the remote side) or running the Flutter commands locally for the device step only. Works with any remote host.
3. **Emulator on the remote host** (x86_64 with KVM) viewed through a forwarded port or `scrcpy`. Only if the host supports it.
4. **No device on the remote host:** build a debug APK there, copy it to the phone through the Downloads page (login protected, `mobile-app-plan.md` 6.4) or `adb install` from the local computer. Slowest loop; fine for CI-style checks.

**Builds and CI** run on GitHub-hosted `ubuntu-latest` as decided in `mobile-app-plan.md` 6.1, so the remote host only needs to be good enough for analysis, unit and widget tests and daily Gradle builds. If the remote host is ARM64, rely on option 1 or 2 for the device and on CI for release builds.

Also in phase 0: answer Q-A1 (app name, application ID); create the Google Play Console account when the first internal test is near (one-time fee); write the privacy page (`/privacy`) text including chat; create the Firebase project (free) and keep its files out of the repository (its `google-services.json` files are kept out of git and supplied to the build by CI).

**Done when:** `flutter doctor` is clean for Android, the chosen device option works with a hello-world build, and `environment.md` says how.

## 3. Backend additions the app needs (before or with the screens that use them)

Each item is one small PR with tests, spec updates (04 API, 02 requirements, 03 data model if tables change) and a runbook line if an operation changes. Items 1 to 4 are already described in `mobile-app-plan.md` section 5.

| # | Item | Needed by | Notes |
|---|---|---|---|
| B1 | `GET /api/v1/app/config`: terminology map (words and slugs), minimum supported app version, latest version | Phase 1 | Public (no login) so the login screen has the right words. Cache headers; no secrets. |
| B2 | Minimum version check: the app sends `X-App-Version` and `X-App-Platform`; if below the minimum, the API still answers normally but `app/config` tells the app to block. | Phase 1 | Never reject API calls from old apps by header alone in v1. |
| B3 | Delete my account (`DELETE /me`, password confirmation) with the anonymising rules | Phase 4 (store requirement) | Ratings and vouches stay, name removed. |
| B4 | Login-protected Downloads API (`/app/downloads`) | Phase 1 (first APK) | As in `mobile-app-plan.md` 6.4. |
| B5 | Device tokens (`POST /devices`, `DELETE /devices/{id}`), `notification_outbox`, the worker's FCM sender | Phase 6 | Shared by chat and later notifications. `PUSH_ENABLED` setting, default false. |
| B6 | Chat REST + WebSocket + moderation + reports RP-09, RP-10 | Phases 5 and 6 | See [chat design](chat-design.md). Split into: schema + rules + REST; WebSocket + hub + LISTEN/NOTIFY; push; moderation and reports. |
| B7 | OpenAPI export stored in the repository (`docs/openapi.json`, checked in CI that it is current) and used to generate the Dart models | Phase 1 | Already on the deferred list. Without it the app drifts from the API. |

## 4. App phases

Week estimates are for one person part time and match `mobile-app-plan.md` section 8 where they overlap.

### Phase 1: scaffold, login, shell (about 3 weeks)

- `mobile/` Flutter project, flavors `demo` and `prod`, application ID from Q-A1 (placeholder until then), Material 3 theme, light and dark, bottom navigation shell (`go_router` `StatefulShellRoute`), Riverpod.
- API client (`dio`), token store (Keystore), refresh on `401`, generated models (B7), error mapping to the same messages as the web.
- `app/config` (B1) -> terminology provider; minimum-version screen.
- Screens: login (per role, no admin), register (freelancer, work host, organisation), forgot and reset password (the reset link opens in the browser in v1), logout, dashboard.
- `ci-mobile` (analyze, format, test with coverage, debug APK artifact), Dependabot for pub and Gradle.
- First signed release APK to the Downloads page (B4) through `mobile-release`.
- **Acceptance:** log in as each of the three roles on a phone against the demo server, see the right words, refresh works, bad password message identical to the web.

### Phase 2: freelancer features (about 2 weeks)

Profile, skills and other labels with levels, rate (as on the web), availability periods (list view on a phone), ratings received, vouches (accept/reject), organisations vouching. Match the web's validation rules exactly (shared rules written down in `mobile/lib/core/validation` with tests ported from `frontend/src/shared/validation.test.ts`).

### Phase 3: work host features (about 2 to 3 weeks)

- Search with filters (skills, level, languages, timing, nativity, organisation, availability dates), name search, sort, paging, active filter chips, filter sheet (full-screen sheet on phones).
- **Mobile number reveal:** the greyed placeholder with a Reveal button on result cards and the detail page; Reveal calls `POST /freelancers/{id}/reveal-mobile` with `channel=dial`, `source` (`search` or `detail`), `searched_skills`, then opens the dialler with a `tel:` intent (`url_launcher`). The number lives only in memory, is never logged and is cleared when the screen is left. A `429` shows the wait time.
- Freelancer detail, rate (create/edit), ratings I gave, my profile.
- **Acceptance:** each web page of the work host has an app equivalent; the reveal events show in report RP-08 with channel `dial`.

### Phase 4: organisation features and account deletion (about 2 weeks)

Vouched list with status, search and vouch, profile, pending-approval state, delete account (B3), settings (about, privacy link, version, log out). **Version 1 without chat is complete here** and can be handed to internal testers.

### Phase 5: chat backend (can start in parallel with phase 2)

Backend items B6 (first two parts) with the spike on sync SQLAlchemy + async WebSocket first. Specs and ADR-0014 first, then code. No app work depends on it until phase 6.

### Phase 6: chat in the app and notifications (about 3 weeks)

- Start a conversation from search result and detail ("Message"), conversation list with unread badges, thread screen (newest at the bottom, load older on scroll, sending/failed states with retry, read marks), mute, block, report.
- WebSocket client: connect when the app is in the foreground and signed in; first-frame auth; heartbeat; reconnect with exponential back-off and jitter; token refresh then reconnect on `4401`; catch-up through REST; outbound queue with `client_message_id` (survives a short offline period, not an app restart in v1).
- Push (B5): Firebase Messaging, Android 13+ notification permission request at a sensible moment (after the first chat, not at launch), notification channel "Messages", tap opens the conversation (deep link `skills://chat/<conversation_id>` handled by `go_router`), token registered after login and removed at logout.
- Notification settings screen (messages on/off).
- **Acceptance:** two phones (or phone + emulator) in a conversation; message arrives in under a second on a good network; app killed -> push arrives -> tap opens the thread; airplane mode then back -> nothing lost, nothing duplicated.

### Phase 7: hardening and release (about 2 weeks)

Accessibility pass (TalkBack, large text, contrast), performance (cold start, list scroll, memory), battery behaviour of the socket (disconnect in background), release APK/AAB, Play internal testing, privacy page and data-safety form including chat, staged rollout notes. Crash reporting stays off in v1.

## 5. Web parity checklist (kept in `docs/android/parity.md`)

One table with a row per web screen and per API endpoint used by the web: status (not started / done / not applicable), app screen, test file. The kick-off prompt tells the new session to create it from `frontend/src/portals` and the OpenAPI file, and to keep it updated in every PR. It is the definition of "all other features should be the same".

## 6. Android-specific details

| Topic | Decision |
|---|---|
| Minimum Android | Android 8.0 (API 26) unless Flutter's own minimum is higher; target the current Play requirement at release time (check then) |
| Network security | HTTPS only (`usesCleartextTraffic=false`) in `prod`; the `demo` flavor also HTTPS. A debug-only exception for `10.0.2.2` is allowed in debug builds. |
| Backups | `android:allowBackup="false"` so tokens and caches are not copied to cloud backup |
| Screenshots | No `FLAG_SECURE` in v1 except on the login/password screens (optional); revisit with the privacy review |
| Logging | Use a logger that is off in release builds; never log request/response bodies, tokens or numbers |
| Obfuscation | `--obfuscate --split-debug-info` for release |
| Permissions | `INTERNET`, `POST_NOTIFICATIONS` (phase 6). No contacts, location, camera or storage permissions. The dialler uses an `ACTION_DIAL` intent, which needs no permission. |
| Deep links | `skills://` custom scheme for notifications in v1; App Links (verified HTTPS) later |
| Background | No foreground service for the socket. Close the socket in the background; rely on push |
| Dialler on devices without a phone app (tablets) | If `canLaunchUrl('tel:')` is false, show the number with a copy button |

## 7. Repository, branches and PRs

- Work in this repository (monorepo, ADR-0007): `mobile/` for the app, `backend/`, `docs/`.
- Branch names `feat/...`, `fix/...`, `docs/...`, `chore/...` like now. Conventional Commit PR titles (release-please). The app is a separate release-please package `mobile` (decision 2 in `mobile-app-plan.md`).
- Required checks never use path filters (so they cannot stay "Expected"); jobs finish quickly when nothing relevant changed.
- No workflow runs for PRs from forks (the fork guard and `scripts/check-fork-guard.py` apply to every new workflow).
- GitHub Actions pinned by SHA; secrets only in environments (`mobile-release`).
- Before every PR: run the checks that can run locally, write `temp/pr-<topic>.md` with the description, list decisions that need confirmation.

## 8. Testing (summary; levels in `mobile-app-plan.md` 3.1)

| Part | Tests |
|---|---|
| Every screen | Widget tests: loading, content, empty, error + retry, validation messages, words under the `default` and `church` profiles, text scale 2.0, semantics |
| Repositories and API client | Unit tests with a fake HTTP layer: auth refresh, 429 handling, error mapping |
| Reveal | Widget + unit: number never shown before the call, dialler launched with the right URI, `429` message, number cleared on leaving |
| Chat client | Unit: outbound queue, dedupe, reconnect back-off (with a fake clock), catch-up; widget: thread states; integration: fake WebSocket server |
| Backend | pytest per `chat-design.md` section 10; migration test; reports tests for RP-09 and RP-10 |
| Contract | CI check that `docs/openapi.json` matches the running API (B7) so generated models cannot drift |
| Release | Emulator smoke test of the release build (app starts, login screen, `/health` reachable) |

Coverage floor 70 % for `lib/` at first (as in `mobile-app-plan.md`), raised later.

## 9. Documents to create or update during the work

| Document | Change |
|---|---|
| `docs/adr/0014-realtime-chat-over-websocket.md` | New: transport choice, LISTEN/NOTIFY, auth frame |
| `docs/adr/0015-flutter-for-the-mobile-apps.md` | New: records decision A1 |
| `docs/specification/02-functional-requirements.md` | New FR for chat, app config, device tokens, account deletion |
| `docs/specification/03-data-model.md` | Chat tables, device tokens, outbox |
| `docs/specification/04-api.md` | All new endpoints and the WebSocket protocol |
| `docs/specification/05-reports.md` | RP-09 chat reports, RP-10 chat metrics |
| `docs/specification/06-frontend.md` | Pointer: the Android app is specified in `docs/android/` |
| `docs/specification/07-non-functional.md` | Chat privacy and retention, push |
| `docs/operations-runbook.md` | WebSocket and proxy timeouts, push secrets, chat limits, moderation steps |
| `docs/mobile-app-plan.md` | Add a pointer to this folder at the top; mark section 8 phases as superseded by `docs/android/plan.md` where they differ |
| `docs/android/environment.md`, `parity.md` | New (phase 0 and 1) |
| `docs/open-questions.md` | Add Q-A1 to Q-A7 |

## 10. Risks

| Risk | Mitigation |
|---|---|
| Android toolchain on the remote host (especially ARM64) | Phase 0 check, device options in section 2, CI for release builds |
| Sync DB layer with async WebSocket | Spike first; fallback is a small async engine for `chat` only |
| LISTEN/NOTIFY drop or load | Catch-up through REST makes loss harmless; load test with the multi-process test; Redis only if measured necessary |
| Battery and OS killing the connection | Foreground-only socket, push as the wake-up, heartbeat, back-off |
| Chat abuse | Rate limits, work-host-only start, block, report, moderation reports |
| API drift between web and app | Generated models from OpenAPI, parity table, contract check in CI |
| Store rules (accounts, privacy, deletion) | Delete account and privacy page in phase 4 and 7; check current rules then |
| Scope creep in chat | Version 1 is text only; "later" list in the chat design is a parking place |
