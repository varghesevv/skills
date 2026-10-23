# Mobile app plan (Flutter, iOS and Android)

Status: proposal for discussion. Nothing here is built yet. Versions of tools and packages are not pinned in this plan; pin them when the project starts and re-check store rules then, because they change.

## 1. Goals

- One Flutter code base that runs on iPhone and Android phones.
- A light, current look: Material 3, bottom navigation bar, large collapsing titles, platform-native back gestures, dark mode.
- Its own release pipeline in the same style as the backend and web: Conventional Commits, automatic versions, signed builds, uploads to the stores' test tracks, and a manual step to go public.
- Uses the existing API as it is (plus a few small additions in section 5). No second backend.

## 2. Scope of version 1

| Role | In the app | Why |
|---|---|---|
| Freelancer (Searcher in the `church` profile) | Yes | Phone is where they update availability and see ratings and vouches |
| Work host (Provider) | Yes | Search, view a person, rate |
| Organisation (Church) | Yes | Vouched list, search and vouching on the phone (phase 4, still part of version 1) |
| Admin | No | Reports and approvals stay on the web. The app has **no admin login screen** and no admin screens; it never sends `user_type=admin`. |

Because the app only ever asks for a freelancer, work host or organisation login, an admin cannot sign in through it. If an admin's address and password are typed on one of those screens the normal "wrong email or password" message appears, as on the web.

The words and the web addresses already depend on the installation profile (`TERMINOLOGY_PROFILE`). The app must show the same words as the web for the server it talks to (section 5, item 1).

## 3. Technical choices

| Topic | Choice | Notes |
|---|---|---|
| UI kit | Flutter stable, Material 3, adaptive page transitions | Looks right on both; predictive back on Android; swipe-back on iOS |
| Navigation | `go_router` with a `StatefulShellRoute` | Bottom `NavigationBar` with 4 tabs; each tab keeps its own stack and scroll position; deep links come for free later |
| State | Riverpod | Small, testable, no code generation needed for v1 |
| HTTP | `dio` with one interceptor for the access token and one refresh on `401` | Same token rules as the web: 15 minute access token, 30 day refresh token |
| Token storage | `flutter_secure_storage` (iOS Keychain, Android Keystore) | Never `shared_preferences`; never log tokens or passwords |
| API models | Generated from the backend OpenAPI file | Fixes drift between API and app; also useful for the web (already on the deferred list) |
| Text | `gen-l10n` (ARB files), English first, term tokens such as `{organisation}` resolved at run time | Same idea as the web |
| Tests | `flutter_test` (unit and widget), a few `integration_test` flows against a mocked API | Add golden tests only for 2 or 3 key screens |
| Lint | `flutter_lints` + `very_good_analysis` rules, `dart format --set-exit-if-changed` | Same strictness as the other parts |

Tabs for a work host: Search, Ratings given, Profile. Tabs for a freelancer: Home, Availability, Ratings and vouches, Profile. Detail pages push on top of the current tab.

### 3.1 Testing

Same bar as the backend and the web: nothing merges with a failing test, and every screen has a test.

| Level | What it covers | Tools | Runs |
|---|---|---|---|
| Unit tests | Pure Dart: models and JSON parsing, validators (the same rules as the web forms), the token store and refresh logic, the terminology tokens (`{organisation}`, `{a_freelancer}`), filter-to-query conversion, date and rate formatting, repositories against a fake HTTP layer | `flutter_test`, `mocktail`, `dio` with a mock adapter | Every PR, seconds |
| Screen (widget) tests | **One test file per screen**: loading, content, empty, error and "try again" states; form validation messages; tapping through the bottom tabs and back; chips and filters on search; the Searcher/Provider words under both the `default` and `church` profiles; large text scale (2.0) and a narrow phone width without overflow; semantics labels exist for buttons and fields | `flutter_test` widget tester, a fake API provided through Riverpod overrides | Every PR |
| Golden (screenshot) tests | Image comparison for 3 to 5 key screens (login, search, person detail, availability), light and dark | `flutter test --update-goldens` locally; goldens are generated on Linux in CI so they never differ by machine | Every PR |
| Integration tests | Whole flows on a real emulator against a mocked API server: log in, search, open a person, rate; freelancer edits availability; token expires and is refreshed; wrong-account message | `integration_test` on the Android emulator | PRs that touch `mobile/`, and before each release |
| Release smoke test | The built release APK installs and starts; the login screen shows; the app talks to the demo server's `/health` | Emulator job in `mobile-release` | Every release |

Rules:
- Coverage is measured (`--coverage`) and reported on every PR; start with a floor of 70 % for `lib/` and raise it as the app grows. Generated code is excluded.
- A test never contacts a real server and never contains a real password; fake values are generated per run, like the backend tests.
- Accessibility checks (`meetsGuideline` for tap target size and labels, contrast in goldens) are part of the screen tests.
- iOS gets the same Dart tests (they are platform independent). Platform-specific behaviour (Keychain, back swipe) is checked by the TestFlight build on a real iPhone before a release.
- Optional later: a device farm (Firebase Test Lab) for a handful of real Android models before a public release.

## 4. Repository layout

A `mobile/` folder in this repository (feature-first):

```
mobile/
  pubspec.yaml            # version: X.Y.Z+build  (kept up to date by release-please)
  lib/
    app/                  # router, theme, shell with the bottom bar
    core/                 # api client, auth, secure storage, terminology, errors
    features/
      auth/  search/  freelancer/  workhost/  ratings/  profile/
  test/  integration_test/
  android/  ios/          # signing is injected by CI, nothing secret is committed
```

Flavors: `demo` (points to the demo server, installs next to production) and `prod`. The server address is a build setting (`--dart-define=API_BASE_URL=...`), not a secret.

## 5. Backend and API additions (small)

1. **Public app config**: `GET /api/v1/app/config` returns the terminology map of the installation (the actual words and slugs, so the app does not carry a copy of `profiles.json`), and the minimum supported app version.
2. **Minimum version check**: if the app is older than the minimum, it shows "please update" and links to the store. This lets the API change safely.
3. **Delete my account**: Apple (and Google) require an in-app way to delete an account when the app lets people create one. Needs an endpoint, the screen, and a rule for ratings and vouches that exist (anonymise, do not break other people's data).
4. **Device sessions**: refresh tokens already exist; add a label (device name) and "log out everywhere" later.
5. **Login-protected downloads**: `GET /api/v1/app/downloads` (list) and `GET /api/v1/app/downloads/android/<version>` (file), any logged-in role, with the downloads folder mounted read-only into the API container (section 6.4). The web app gets a Downloads page.
6. **A demo account for store review**: reviewers need a working login. Use the demo server with a clearly named review account; its password goes only into the store consoles, never into the repository.

## 6. CI/CD

### 6.1 What can run on the Raspberry Pi

Short answer: not the builds.
- **iOS** builds need macOS and Xcode. A Pi cannot do this at all.
- **Android** builds on a 64-bit ARM Linux host are not an officially supported Flutter setup (Flutter lists Linux ARM64 as a host for Linux and web targets; the Android SDK tools are the weak point). It may work with effort, but it is fragile and slow on a Pi.
- What the Pi could do: `dart analyze`, `dart format` and unit/widget tests. That is not worth a second toolchain to maintain.

**Recommendation:** use GitHub-hosted runners for all mobile jobs: `ubuntu-latest` for checks and Android, `macos-latest` for iOS. Standard hosted runners are free for public repositories (check the current terms if the repository becomes private; macOS minutes are then billed at a higher rate). Keep the Pi for what it already does.

### 6.2 Pull requests: `ci-mobile`

Same rules as the other checks: always runs (no path filters, so the required check never stays "Expected"), job names equal the required check names.
- `mobile-analyze`: `flutter pub get`, `dart format --set-exit-if-changed`, `flutter analyze`.
- `mobile-test`: `flutter test --coverage`; the integration flows run on the Android emulator only when a PR changes `mobile/` (they are slower).
- `mobile-build-android`: builds a debug APK and keeps it as a build artifact for testers (expires after a few days).
- Jobs exit early and succeed when the PR changes nothing under `mobile/`.
- Dependabot for the `pub` ecosystem and for the Gradle and CocoaPods dependencies; the secret scan already covers the repository; third-party actions pinned to commit SHAs like the others.

### 6.3 Versions and releases

- The app version is `X.Y.Z+N` in `pubspec.yaml`. `X.Y.Z` comes from release-please. `N` (the build number the stores require to increase) is the workflow run number.
- Decision needed (Q2): either one version for the whole product (simplest) or a separate release-please package `mobile` with tags `mobile-vX.Y.Z` so the app can ship independently of the web. I recommend the **separate package**, because store reviews and web deploys run on different rhythms.
- `mobile-release.yml` runs when the mobile release is published (or manually):

| Job | Runner | Steps | Result |
|---|---|---|---|
| `android-release` | ubuntu | restore the upload keystore from a secret, `flutter build appbundle --release --obfuscate --split-debug-info`, upload with `fastlane supply` or a pinned upload action | New build on the Play **internal testing** track |
| `ios-release` | macos | install the signing certificate and profile (App Store Connect API key + `fastlane match` in a private repository), `flutter build ipa --release --obfuscate --split-debug-info`, upload with `fastlane pilot` | New build on **TestFlight** |

- All signing material and store keys live in the GitHub Environment `mobile-release` with **required reviewers**. They are written to temporary files with mode 600, removed at the end, and never echoed.
- **Going public is a manual step** in the store consoles (Play: promote internal → closed → production; App Store: submit the TestFlight build for review). Staged rollout (for example 10%, then 100%) on Android.
- Debug symbols (Dart split-debug-info) are kept as release artifacts, so a crash report can be read later if crash reporting is added. There is no crash reporting service in version 1.

### 6.4 Test downloads on the web server (only after login)

Testers who have an account can download Android builds from the demo site, with the version in the file name. Nobody who is not logged in can see or fetch a build.

- **Where people find it:** a **Downloads** page in the web app (`/downloads`, linked from the account menu), available to every logged-in account. It lists the newest build first, then older versions, each with version, build number, date, size, SHA-256 and the release notes (from the changelog).
- **Where the files live:** `/opt/skills/data/downloads/android/<version>/skills-demo-<version>.apk` on the server, plus a generated `index.json`. The folder is mounted **read-only into the API container**. The proxy does not serve it, so there is no public file address at all.
- **API (new, small):** `GET /api/v1/app/downloads` returns the list (login required, any role); `GET /api/v1/app/downloads/android/<version>` streams the APK (login required, the same bearer token as everything else, rate limited, every download counted in the log without personal data). The version in the path is checked against `index.json`, so no path can escape the folder.
- **Browser behaviour:** the page downloads the file with the login token and saves it, so no token ever appears in an address or in the proxy logs. (A short-lived single-use link is the alternative if very large files are needed; for an APK of a few tens of MB the direct download is simpler and safer.)
- **How a build gets there:** after `android-release` succeeds, a `publish-downloads` job in `mobile-release.yml` copies the APK to the server over SSH, the same way `deploy-demo` already reaches it (temporary port-22 rule for the runner, restored afterwards, same environment protection), updates `index.json` and removes all but the newest 10 versions. The APK is also attached to the GitHub Release as a permanent copy.
- **Android:** testers log in on the phone's browser, open Downloads, install the APK and allow "install from this source" once. The release APK is signed and the SHA-256 is shown so it can be verified. A build installed this way and a Play Store build use different signatures, so a tester uses one or the other.
- **iPhone:** a file on a web server cannot be installed on an iPhone. The Downloads page shows the **TestFlight link** (section 7.1) to logged-in users instead of a file.
- **What is never published here:** debug builds, unsigned builds, symbol files and anything with keys. PR builds stay as short-lived workflow artifacts.
- **In-app update hint:** `app-config` returns the latest version; the app can show "version 1.5.0 is available" and open Downloads (Android) or TestFlight (iPhone).

## 7. Accounts and store rules (check current terms when you start)

| Item | Detail |
|---|---|
| Apple Developer Program | About US$99 per year. An organisation account also needs a D-U-N-S number. |
| Google Play Console | One-time fee of about US$25. New personal accounts must run a closed test with a minimum number of testers for a minimum number of days before production access. |
| Needed for both | App name and bundle ID / application ID (cannot change later), privacy policy page, data safety / privacy labels, support email, screenshots, age rating |
| Apple review | Demo login for the reviewer; account deletion inside the app; no payments in the app (none planned) |
| Private distribution | If this is for one organisation only: TestFlight (builds expire after 90 days) and Google internal testing avoid a public listing. Apple also has "unlisted" and custom app distribution. |

### 7.1 iPhone in plain words (the cost-effective path)

- **What Apple requires:** to put an app on other people's iPhones you must pay for the **Apple Developer Program, about US$99 per year**. There is no free way around this (a free account only runs your own app on your own phone and it stops working after 7 days).
- **TestFlight comes with that fee** at no extra cost. It is Apple's own app for testing: you upload a build, testers install the free "TestFlight" app and tap your invite or public link. Builds stay usable for 90 days, then you upload a newer one.
- **Two kinds of testers:** *internal* (people you add to your Apple team, up to 100, available within minutes) and *external* (up to 10,000 through a public link; the first build of each version goes through a short Apple check, usually a day or so). Start with internal, use the public link when more people join.
- **No Mac to buy:** the iOS build runs on GitHub's macOS runner (free for a public repository). You already have a Mac for the occasional Xcode step, such as the first project setup.
- **Signing without extra infrastructure:** use an App Store Connect API key (stored only in the `mobile-release` environment) and let the build create and refresh the certificates and profiles itself. Only if that proves unreliable, fall back to `fastlane match` with a private repository.
- **What I recommend not to do:** ad-hoc installs from a web server (each phone must be registered, 100 devices per year) and the Enterprise programme (not allowed for this kind of use).
- **Order of work, to spend money late:** build and test **Android first** (Google Play is a one-time US$25, or just the web downloads at no cost). The Flutter code is the same, so adding iPhone later is mostly the US$99 fee plus the pipeline job. Pay Apple when the first iPhone testers are actually waiting (phase 3).
- **Individual or organisation account:** an individual account is quickest (the seller name shown is your own name). An organisation account shows the organisation's name and needs a legal entity and a free D-U-N-S number; choose it only if the name matters.

## 8. Phases (rough, one person part time)

| Phase | Content | Weeks |
|---|---|---|
| 0 | Open item (section 11: app name and IDs), developer accounts, privacy policy page on the website | 1 |
| 1 | `mobile/` scaffold, theme and shell with bottom navigation, API client and generated models, login, token refresh, app-config and terminology, `ci-mobile` with the test levels of section 3.1, first signed APK on the login-protected Downloads page (Android first) | 3 |
| 2 | Freelancer: profile, skills and labels, availability, ratings, vouches | 2 |
| 3 | Work host: search with filters, chips, name search; person detail; rate; ratings given. **Apple Developer account, iOS build to TestFlight (internal testers)** | 2 to 3 |
| 4 | Organisation: vouched list, search and vouching; delete account; settings. **Version 1 is complete here** | 1 to 2 |
| 6 (later) | Push notifications (section 10) | 2 |
| 5 | Accessibility (large text, screen reader), dark mode polish, performance, store listing, review, staged release | 2 |

## 9. Decisions taken

| # | Question | Decision |
|---|---|---|
| 1 | Roles in version 1 | Freelancer, work host and organisation. No admin. |
| 2 | Versioning | Independent mobile versions and releases: tags `mobile-vX.Y.Z` (separate release-please package `mobile`, section 6.3). |
| 3 | Distribution | Internal testing first: the login-protected Downloads page (Android) and TestFlight internal testers (iPhone). No public store listing yet. |
| 4 | Store accounts | Personal accounts (Apple individual, Google personal). |
| 5 | Push notifications | Wanted, in a later phase (section 10). |
| 6 | Crash reporting | None for now. |
| 7 | Other languages, right to left | Not planned. English only; texts still go through `gen-l10n` so a language can be added later. |
| 8 | Downloads page access | Only after login, through the API (section 6.4). |
| 9 | iPhone testing | TestFlight only; Android first, Apple account when the first iPhone testers are waiting (section 7.1). |

A personal Google Play account must complete a closed test (a minimum number of testers for a minimum number of days) before it can publish publicly. Internal-first fits this: when a public listing is wanted, that closed test runs first. Check the current numbers then.

## 10. Push notifications (later phase)

- **What people get:** a freelancer is told about a new vouch request, a new rating and an accepted vouch; an organisation is told when an admin approves or rejects it; a work host gets nothing by default. Each kind can be switched off in Settings.
- **How:** Firebase Cloud Messaging (free) for Android, and for iPhone through Apple's push service using a push key from the Apple Developer account (no extra fee).
- **Backend:** a `device_tokens` table (account, platform, token, last seen, app version); register and remove the token at login and logout; an outbox table written in the same transaction as the event, and the existing worker sends the messages and removes tokens that Apple or Google report as dead. A failed push never blocks the action that caused it.
- **Content and privacy:** the message holds only a short text and an id; the app fetches the details after opening, so nothing sensitive sits on a lock screen or in Google's or Apple's systems. Words follow the installation's terminology.
- **Secrets:** the Firebase service-account key and the Apple push key are environment secrets of the server, supplied like the other secrets, never in the repository or logs.
- **Tests:** unit tests for token handling and the outbox, an API test per event, a widget test for the Settings switches, and a manual check on a real phone of each platform before release.

## 11. Still open

1. App name and the bundle ID / application ID. To be provided by the owner. They cannot be changed after the first upload, so they are needed before phase 1 ends (the first signed build and the store records use them).

Decided: the privacy policy is a public page on the demo website (for example `/privacy`). The store consoles need its address, so it must exist, without a login, before the first TestFlight or Play upload. It covers what is collected (account details, skills, rates, ratings, vouches, push tokens later), why, who sees it, how long it is kept, how to delete the account, and a contact address. A page for support or contact can sit beside it.
