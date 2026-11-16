# Releasing the Android app

How a signed build of the app reaches the demo server and the testers' phones. The workflow is `.github/workflows/mobile-release.yml` ("mobile-release" under Actions). It runs by hand and never on its own.

## What it does

1. Reads the version from `mobile/pubspec.yaml` (`version: 1.2.3` or `1.2.3+4`; the part after `+` is ignored). The **build number is the run number** of the workflow, so it grows with every run.
2. Builds a **release** APK of the `demo` flavor, signed with your release key, pointing at `https://<SITE_ADDRESS>/api/v1`, with `PRIVACY_URL=https://<SITE_ADDRESS>/privacy` (the Privacy row of the settings).
3. Checks the signature with `apksigner` and that the certificate is the release certificate (`ANDROID_CERT_SHA256`). An unsigned build, or one signed with another key, fails the run. The build is obfuscated; the symbol files are kept as a workflow artifact for 90 days, to decode crash traces.
4. Copies the APK to `/opt/skills/data/downloads` on the server with `scripts/add-download.py` (it keeps the newest 10 versions). The Android app page of the web app and `GET /api/v1/app/downloads` list it for signed-in people; there is no public address for the file.
5. If you give a release tag (for example `skills-v1.0.0`) it also attaches the APK to that GitHub release.

The signing key is decoded for the build only and deleted afterwards; nothing secret is printed. It runs only on `main`, has no build cache of its own (a shared cache must not run next to the key), and shares the `deploy-demo` concurrency group because both open and restore the server's SSH rule.

## What you provide (once)

All of these go in the GitHub **Environment `demo`** (Settings > Environments > demo). The rows marked Existing are already used by the deploy.

| Kind | Name | What it is |
|---|---|---|
| Secret | `ANDROID_KEYSTORE_BASE64` | The release keystore file, base64 on one line |
| Secret | `ANDROID_KEYSTORE_PASSWORD` | The keystore password |
| Secret | `ANDROID_KEY_ALIAS` | The key's alias in the keystore |
| Secret | `ANDROID_KEY_PASSWORD` | The key's password |
| Variable | `ANDROID_CERT_SHA256` | The SHA-256 fingerprint of the release certificate (see below); the run fails when the APK is signed with anything else |
| Variable | `APP_MIN_VERSION`, `APP_LATEST_VERSION` | `1.2.3`; the minimum the server accepts and the newest it offers. `deploy-demo` writes them (S7.2a); default `0.0.0` |
| Existing | `DEPLOY_SSH_PRIVATE_KEY`, `AWS_DEPLOY_ROLE_ARN`, `SERVER_HOST`, `SITE_ADDRESS`, `TF_SSH_ALLOWED_CIDRS` | Used to reach the server |

### Make the key

Do this on your own computer, not on a server or in the repository:

```bash
keytool -genkeypair -v -keystore skills-release.jks -alias skills -keyalg RSA -keysize 4096 -validity 10000
```

It asks for the two passwords and a name. **Back the file and the passwords up in two places** (a password manager and an offline copy). A build signed with a different key cannot update an installed app: if you lose the key, every phone has to uninstall first. Never commit the file; Git ignores `*.jks`.

Read its fingerprint (it is public) and keep it for the Environment variable `ANDROID_CERT_SHA256`:

```bash
keytool -list -v -keystore skills-release.jks -alias skills | grep 'SHA256:'
```

### Put it in the Environment

The values are read from files and the keyboard so that they do not end up in your shell history or on screen:

```bash
base64 -w0 skills-release.jks | gh secret set ANDROID_KEYSTORE_BASE64 --env demo
gh secret set ANDROID_KEYSTORE_PASSWORD --env demo     # it prompts; paste, press Enter
gh secret set ANDROID_KEY_ALIAS --env demo
gh secret set ANDROID_KEY_PASSWORD --env demo
```

(On macOS use `base64 -i skills-release.jks | tr -d '\n'`.) Then set the fingerprint: `gh variable set ANDROID_CERT_SHA256 --env demo --body '<the SHA256 value>'`.

**Restrict the Environment to `main`**: Settings > Environments > demo > Deployment branches and tags > Selected branches > `main`. The workflow also refuses to run anywhere else, but the Environment is what keeps the key from a run on another branch.

## Run it

1. Set `version:` in `mobile/pubspec.yaml` and merge that change.
2. Actions > mobile-release > Run workflow. Optionally give release notes (shown on the Android app page) and a release tag.
3. When it is green, open the Android app page of the web app, or ask the API: the new version is listed with its SHA-256. A tester can check it with `sha256sum`.
4. To make older builds ask people to update, set `APP_MIN_VERSION` and `APP_LATEST_VERSION` in the Environment and run `deploy-demo` again.

## Push notifications (needs your Firebase project)

Chat works without push: the app shows new messages while it is open. To notify a phone whose app is closed, push needs a Firebase project, which only you can create (free). Until then the app builds and runs with no push: without `google-services.json` in the build, Firebase does not start in the app, so the person is never asked to allow notifications, and without `PUSH_ENABLED` on the server nothing is sent.

1. In the Firebase console create a project. Add an Android app for each build you install: the demo flavor's ID is the application ID with `.demo` after it (now `com.example.skills.dev.demo`, see Q-A1 below), the store flavor's is the application ID itself.
2. Download `google-services.json` once, after both apps are added: that one file lists both application IDs, and the build uses it for either flavor. It is not a secret in the way a key is, but it belongs to your project: keep it out of git (`mobile/android/.gitignore` ignores `mobile/android/app/google-services.json`). A build uses the file when it is in that place; without it there is no push.
3. For release builds, store the file in the `demo` Environment as a secret (for example `ANDROID_GOOGLE_SERVICES_JSON`, base64) and have the release workflow write it to `mobile/android/app/google-services.json` before the build. **This workflow step is not made yet:** it touches `.github/`, so it is made together with you (S9.2).
4. For the server: Firebase console > Project settings > Service accounts > Generate new private key. Put the JSON in the API worker's environment as `FCM_SERVICE_ACCOUNT_JSON` and set `PUSH_ENABLED=true` for the API and the worker (operations runbook, "Chat push"). The key is a secret: environment only, never a file in the repository (ADR-0011).
5. Check on a phone: sign in as two people, open Messages on the first phone (allow notifications), close the app, write from the second. A notification "You have a new message" arrives within a few seconds, with no text in it; tapping it opens the conversation.

The push only says that there is a new message and which conversation; it never carries text or names. At sign-out the phone is removed from the server; if a session ends without signing out, the next person to sign in on that phone replaces the address.

## How this follows ADR-0011 (secrets from the environment only)

- **No secret in the repository** (1): the workflow only names secrets (`secrets.ANDROID_*`); the key, its passwords and the SSH key exist only in the Environment. `*.jks`, `*.keystore` and `key.properties` are git-ignored, and `scripts/check-secrets.sh` (the required `secrets-scan` check) refuses them if they are added anyway.
- **Environment variables only, no defaults, a clear error** (2, 3): Gradle reads the key from `ANDROID_KEYSTORE_FILE` and the three other `ANDROID_*` variables; if one is missing the build stops and names it. The workflow checks every setting first and refuses a value that is not one line, as `deploy-demo` does.
- **Nothing in logs** (5): secrets are passed as step environment variables (GitHub masks them), never on a command line or in a printed line; the decoded key is written with mode 600 in the runner's temporary folder and deleted in the build step and again in the last step, which always runs. The signature check prints the certificate's name and SHA-256 only, which are public.
- **Nothing to run from outside**: the workflow starts only by hand (`workflow_dispatch`), the release notes and the tag are read through the environment, never pasted into a script, and the tag is checked before use.

## Staged rollout of the first release with chat (S9.3)

Order matters: the server first, the app after, push last.

1. **Server and web (the pull request from `feat/chat` into `main`).** Merging it deploys the demo, including the migrations `0019` to `0021` (chat tables, reports, push addresses). The older app keeps working: nothing it uses has changed. Check the runbook's "Chat limits" and "The chat socket" sections, and that `--ws-max-size 16384` is on the API container (it is in `docker-compose.yml` and `infra/docker/compose.demo.yml`).
2. **The app to testers.** Run `mobile-release` on `main` (see "Run it"); testers download it from the Android app page. Ask two or three testers to write to each other for a few days. Push is still off.
3. **Push, when the Firebase project exists.** Follow "Push notifications" above, then set `PUSH_ENABLED=true` for the API and the worker and run the check in step 5 of that section. Switch it back off by setting it to `false` and restarting: chat itself carries on.
4. **Google Play (when the store account exists).** Internal testing, then closed testing (a new personal account must run a closed test with a minimum number of testers for a minimum number of days before production access), then **production at 5%, 20%, 50%, 100%**, at least two days at each step. The store forms are answered from `docs/android/store-data-safety.md`.

**Before each step up** look at, in this order: the crash and error numbers in the store console; the API log for a rise in `429` (the chat limits), `403 chat_blocked` and `5xx` on `/api/v1/chat`; the report `chat_reports` (RP-10: reports per week, open ones) and `chat_metrics` (RP-11: first answers, median time); the worker log for "Chat push run failed". Go on only when nothing is rising. Reports of harassment or scams stop the rollout until the OWNER has read them (the readings are logged) and decided.

**To stop.** In the Play console halt the rollout (people who have the new version keep it). There is no switch to turn chat off for everyone: if a serious problem is on the server side, block `/api/v1/chat` at the reverse proxy (people see an error where messages are), fix it and open it again. A dangerous app version is retired with `APP_MIN_VERSION` (then older apps ask for an update). Always fix forward with a higher version code; a store cannot go back to a lower one.

**Before the first public release, the owner has to have done** (everything here is the owner's, see the roadmap section 7): the signing key and `ANDROID_*` secrets; the application ID (Q-A1: it cannot change after the first store upload); the Firebase project and its files; reading the privacy page; and the store account with the filled forms.

## Things to know

- **The application ID is a placeholder** (`com.example.skills.dev`, open question Q-A1). It cannot change once a build is installed or uploaded to a store: a new ID is a different app. Decide the name and ID before testers depend on the app, and before any store upload.
- The demo flavor installs next to a `prod` flavor (`.demo` suffix). Store builds (the `prod` flavor) are S9.
- Only builds made by this workflow belong in the downloads folder: `add-download.py` cannot tell a debug build from a release build.
- If the run fails after "Open SSH for this runner", the last step still restores the SSH rule; if it printed a warning, run `terraform apply` as the runbook says.
