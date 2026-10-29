# Kick-off prompt for the Android development session

Paste the text between the lines into the first message of the new Claude Code session (VS Code, Remote-SSH, opened on the repository root). Update the bracketed values first.

---

You are starting development of the **Android application** for the Skills project in this repository (monorepo: `backend/` FastAPI + PostgreSQL, `frontend/` React, `docs/`, `infra/`). You can run commands on this machine: use that to check and verify, and do not guess.

**Read first, in this order, completely:**
1. `docs/android/understanding.md`
2. `docs/android/plan.md`
3. `docs/android/chat-design.md`
4. `docs/mobile-app-plan.md` (the earlier Flutter plan; where it differs, `docs/android/` wins for Android)
5. `docs/specification/` (all files; especially 02, 04, 06, 07), `docs/operations-runbook.md`, `docs/product-understanding.md` if present on this branch, `CONTRIBUTING.md`, `docs/adr/`
6. For API behaviour: `backend/app/api/v1/*.py`, `backend/app/schemas/*.py`; for the web behaviour you must match: `frontend/src/portals/`, `frontend/src/shared/`, `frontend/src/terminology/`

**Goal.** Build an Android app (Flutter, Material 3) that has every feature of the web application for freelancers, work hosts and organisations (no admin screens), using the **same `/api/v1` API**, plus a **chat** between work host and freelancer with real-time delivery (WebSocket) and push notifications (FCM). Add whatever API endpoints are needed, in separate backend PRs, so that the web can use them too.

**Rules you must follow (they come from the owner's standing instructions):**
- **Never write any password, token or secret into source, logs, tests, docs or screenshots.** Secrets come from environment variables only. Never log tokens, passwords, message bodies or phone numbers. Test credentials are generated at run time. If you need a secret value, tell me what variable to set; do not invent one.
- Do not weaken the existing secret checks (`scripts/check-secrets.sh`, `validate_secrets`); extend them for new secrets (Firebase key, signing keys).
- No GitHub workflow may run for pull requests from forks (fork guard on every `pull_request` job; keep `scripts/check-fork-guard.py` passing). Pin third-party actions to commit SHAs.
- Words for the roles come from the server (`GET /api/v1/app/config`, which you will add); the app never hard-codes "Provider", "Searcher", "Church" or similar. Stored `user_type` values and API paths never change with wording.
- The mobile number of a freelancer is returned only by `POST /api/v1/freelancers/{id}/reveal-mobile`; the app must implement Reveal exactly as in `docs/android/plan.md` phase 3.
- Conventional Commit titles (release-please), one topic per branch and PR, tests with the code, specs and runbook updated in the same PR, `git add <paths>` and never `git add -A` (the root may contain private untracked files such as `temp/`). Keep private team notes (church name, pricing, domain, legal) out of the repository.
- Commit or push only when I ask. When a PR is ready, write the description to `temp/pr-<topic>.md` (ending with the attribution lines the session gives you) and print the exact `git add` / `git commit` commands. List the decisions I must confirm.
- Ask me only when a decision is genuinely mine and blocks you (for example Q-A1, the app name and application ID). For everything else choose the documented default, say which one you chose, and carry on.

**Do this now, in order:**
1. **Phase 0.** Run the environment checks from `docs/android/plan.md` section 2 on this machine (architecture, Java, Flutter, Android SDK, KVM, `adb devices`, disk, RAM). Do not install anything system-wide without telling me what and why; prefer user-level installs under my home directory. Write the findings and the chosen way of running the app on a device to `docs/android/environment.md`. Tell me what I must do myself (for example attach a phone, enable wireless debugging, install a missing package that needs sudo).
2. Create `docs/android/parity.md`: one row per web page and per API endpoint used by the web (read `frontend/src/portals`, `frontend/src/api`, and the OpenAPI document from `backend`), with status columns. Keep it current in every later PR.
3. Create a task list for phases 1 to 7 from the plan. Show me the list and the order, then start phase 1. In parallel, propose the first backend PRs (B1, B7, then B4) and the chat spike from `docs/android/chat-design.md` section 6 with its result written down before the rest of the chat backend is built.
4. For each phase: implement, run the tests and linters that exist (`flutter analyze`, `dart format --set-exit-if-changed`, `flutter test`; for backend `ruff` and `pytest` as in `Makefile`/`docs/local-development.md`; for web `npm` scripts if the web changes), fix failures, then prepare the PR files. Say plainly what you could not run and why.
5. Keep `docs/android/*.md`, the specs and the ADRs (0014 realtime chat, 0015 Flutter) up to date as decisions are made. Add Q-A1 to Q-A7 to `docs/open-questions.md`, and add a pointer to `docs/android/` at the top of `docs/mobile-app-plan.md`.

**Definition of done for each phase** is in `docs/android/plan.md`. Version 1 without chat is done at the end of phase 4; chat at the end of phase 6.

Start with step 1 and report what you find before changing anything else.

---
