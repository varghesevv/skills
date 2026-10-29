# Android application: understanding

Status: draft for review. Written 2026-10-29. Nothing in this folder is built yet.
Companions: [plan](plan.md), [chat design](chat-design.md), [kick-off prompt](kickoff-prompt.md).
Builds on: [mobile-app-plan.md](../mobile-app-plan.md) (the earlier Flutter plan, iOS and Android). Where the two differ, this folder wins for Android work and `mobile-app-plan.md` stays the reference for iPhone and the store rules.

## 1. What is being asked

1. An **Android app** for the Skills project that offers everything the web application offers for freelancers, work hosts and organisations (admin stays on the web, as already decided).
2. The app and the web front end use **the same REST API** (`/api/v1`). No second backend, no behaviour that only exists in the app. Where the app needs something new, it is added to the API so the web can use it too.
3. One feature that is **new for the app**: **chat** between a work host and a freelancer, with **notifications** and **real-time delivery**. The API gets the endpoints for it, including a WebSocket (gRPC was considered and not chosen, see [chat design](chat-design.md) section 2).
4. Development happens in **Visual Studio Code over Remote-SSH, with Claude Code**, in a new session that starts from these documents.

## 2. Decisions taken in this draft (change them here if you disagree)

| # | Topic | Decision | Why |
|---|---|---|---|
| A1 | Technology | **Flutter** (Dart), Material 3, Android first; iPhone stays possible later from the same code | Already chosen in `mobile-app-plan.md`. Works fully from VS Code (no Android Studio needed for daily work). One code base keeps the iPhone option open. Native Kotlin would be a second plan with no reuse. |
| A2 | Scope | Freelancer, work host, organisation. No admin login screen. | Same as `mobile-app-plan.md` section 2. |
| A3 | Parity | Every web feature for those three roles, including the new **mobile number reveal** (Reveal calls the reveal endpoint, then opens the dialler) | The app must not be a reduced client. |
| A4 | Chat | Android first. The API is shared, so the web can add chat later without server changes. | You asked for chat as an app feature. |
| A5 | Realtime transport | **WebSocket** on FastAPI, with REST for history and as a fallback; **PostgreSQL LISTEN/NOTIFY** to reach every API process | Fits the stack (PostgreSQL is the only database, ADR-0002). gRPC would add a second protocol stack and needs end-to-end HTTP/2. |
| A6 | Push | **Firebase Cloud Messaging** for messages while the app is closed, sent by the existing worker from an outbox | Matches section 10 of `mobile-app-plan.md`. Message text is never put in the push. |
| A7 | Who may start a chat | Only a **work host** can start a conversation with a freelancer. The freelancer can reply, mute, block and report. | Stops unsolicited messages to freelancers and matches how the marketplace works (a host looks for a person). |
| A8 | Distribution | Internal first: the login-protected Downloads page and Google Play internal testing. No public listing yet. | Decision 3 in `mobile-app-plan.md`. |

## 3. What stays the same

- **Roles and words.** Stored `user_type` values (`freelancer`, `workhost`, `organisation`, `admin`) and API paths never change. All user-visible words come from the installation's terminology profile (`GET /api/v1/app/config`, new, planned in `mobile-app-plan.md` section 5). The app never hard-codes "Provider", "Searcher" or "Church".
- **Auth.** Argon2id passwords, 15 minute access token, rotating 30 day refresh token, stored only in Android Keystore (`flutter_secure_storage`). Tokens, passwords and phone numbers are never written to logs.
- **Secrets.** No secret in the repository. The server address is a build setting (`--dart-define`), not a secret. The Firebase service-account key and signing keys are environment/CI secrets.
- **Search rules.** A freelancer is listed with at least one skill; results never contain email or mobile number; page size at most 100.
- **Mobile number.** Only the reveal endpoint returns it, every reveal is recorded and rate limited. On Android the channel is always `dial` (the dialler opens).
- **Process.** Conventional Commit titles, one topic per PR, tests with the code, specs and runbook updated in the same PR, no workflows run for PRs from forks, no `git add -A`.

## 4. What is new

| Area | New | Where |
|---|---|---|
| App | `mobile/` Flutter project, flavors `demo` and `prod` | repository `mobile/` |
| API | `app/config`, minimum version, delete my account, device tokens, chat (REST + WebSocket), blocks and reports | `backend/` |
| Worker | Push sender (FCM) with outbox | `backend/app/worker` |
| CI/CD | `ci-mobile`, `mobile-release` | `.github/workflows` |
| Docs | Specs 02, 03, 04, 06, 07, runbook, ADRs for realtime transport and for Flutter | `docs/` |

## 5. Constraints to respect

- **Do not break `/api/v1`** once the app ships; additions only (`/api/v2` for breaking changes).
- **Privacy.** Chat is personal data. The privacy page must mention messages, how long they are kept, deletion, and who can read them (only the two people, and an admin only for a reported conversation). Push messages carry no message text.
- **Abuse.** Chat can bypass the reveal limit by sharing numbers in messages. That is accepted (people may agree to share), but starting conversations is rate limited, messages are rate limited, and a freelancer can block and report.
- **One API instance today** (Lightsail demo), several on ECS later (ADR-0012). The chat design must work with several API processes from the start.
- **Build host.** The Android toolchain is the weak point on ARM64 Linux (see `mobile-app-plan.md` section 6.1). The development host reached over Remote-SSH must be checked in phase 0 (plan section 2).

## 6. Open questions (answer before or during phase 0)

| # | Question | Default if not answered |
|---|---|---|
| Q-A1 | App name and application ID (cannot change after the first upload) | Blocking for phase 1's first signed build only. Use `com.example.skills.dev` locally until decided. |
| Q-A2 | What machine does Remote-SSH connect to (CPU architecture, KVM, a phone attached)? | Check in phase 0; plan section 2 lists the options. |
| Q-A3 | May an admin read a conversation? | Only conversations that someone reported, and the access is logged. |
| Q-A4 | How long are messages kept? | Until either account is deleted, then anonymised; revisit with the privacy page. |
| Q-A5 | Should freelancers be able to start a chat after a work host has revealed their number? | No (A7). Revisit with real usage. |
| Q-A6 | Attachments (photos, documents) in chat? | Text only in version 1. |
| Q-A7 | Chat on the web? | Later; the API already supports it. |
