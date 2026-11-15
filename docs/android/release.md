# Releasing the Android app

How a signed build of the app reaches the demo server and the testers' phones. The workflow is `.github/workflows/mobile-release.yml` ("mobile-release" under Actions). It runs by hand and never on its own.

## What it does

1. Reads the version from `mobile/pubspec.yaml` (`version: 1.2.3` or `1.2.3+4`; the part after `+` is ignored). The **build number is the run number** of the workflow, so it grows with every run.
2. Builds a **release** APK of the `demo` flavor, signed with your release key, pointing at `https://<SITE_ADDRESS>/api/v1`, with `PRIVACY_URL=https://<SITE_ADDRESS>/privacy` (the Privacy row of the settings).
3. Checks the signature with `apksigner`. An unsigned build fails the run.
4. Copies the APK to `/opt/skills/data/downloads` on the server with `scripts/add-download.py` (it keeps the newest 10 versions). The Android app page of the web app and `GET /api/v1/app/downloads` list it for signed-in people; there is no public address for the file.
5. If you give a release tag (for example `skills-v1.0.0`) it also attaches the APK to that GitHub release.

The signing key is decoded for the build only and deleted afterwards; nothing secret is printed. The workflow shares the `deploy-demo` concurrency group because both open and restore the server's SSH rule.

## What you provide (once)

All of these go in the GitHub **Environment `demo`** (Settings > Environments > demo). The deploy already uses the last four.

| Kind | Name | What it is |
|---|---|---|
| Secret | `ANDROID_KEYSTORE_BASE64` | The release keystore file, base64 on one line |
| Secret | `ANDROID_KEYSTORE_PASSWORD` | The keystore password |
| Secret | `ANDROID_KEY_ALIAS` | The key's alias in the keystore |
| Secret | `ANDROID_KEY_PASSWORD` | The key's password |
| Variable | `APP_MIN_VERSION`, `APP_LATEST_VERSION` | `1.2.3`; the minimum the server accepts and the newest it offers (deploy-demo writes them; default `0.0.0`) |
| Existing | `DEPLOY_SSH_PRIVATE_KEY`, `AWS_DEPLOY_ROLE_ARN`, `SERVER_HOST`, `SITE_ADDRESS`, `TF_SSH_ALLOWED_CIDRS` | Used to reach the server |

### Make the key

Do this on your own computer, not on a server or in the repository:

```bash
keytool -genkeypair -v -keystore skills-release.jks -alias skills -keyalg RSA -keysize 4096 -validity 10000
```

It asks for the two passwords and a name. **Back the file and the passwords up in two places** (a password manager and an offline copy). A build signed with a different key cannot update an installed app: if you lose the key, every phone has to uninstall first. Never commit the file; Git ignores `*.jks`.

### Put it in the Environment

The values are read from files and the keyboard so that they do not end up in your shell history or on screen:

```bash
base64 -w0 skills-release.jks | gh secret set ANDROID_KEYSTORE_BASE64 --env demo
gh secret set ANDROID_KEYSTORE_PASSWORD --env demo     # it prompts; paste, press Enter
gh secret set ANDROID_KEY_ALIAS --env demo
gh secret set ANDROID_KEY_PASSWORD --env demo
```

(On macOS use `base64 -i skills-release.jks | tr -d '\n'`.)

## Run it

1. Set `version:` in `mobile/pubspec.yaml` and merge that change.
2. Actions > mobile-release > Run workflow. Optionally give release notes (shown on the Android app page) and a release tag.
3. When it is green, open the Android app page of the web app, or ask the API: the new version is listed with its SHA-256. A tester can check it with `sha256sum`.
4. To make older builds ask people to update, set `APP_MIN_VERSION` (and `APP_LATEST_VERSION`) in the Environment and run `deploy-demo` again.

## Things to know

- **The application ID is a placeholder** (`com.example.skills.dev`, open question Q-A1). It cannot change once a build is installed or uploaded to a store: a new ID is a different app. Decide the name and ID before testers depend on the app, and before any store upload.
- The demo flavor installs next to a `prod` flavor (`.demo` suffix). Store builds (the `prod` flavor) are S9.
- Only builds made by this workflow belong in the downloads folder: `add-download.py` cannot tell a debug build from a release build.
- If the run fails after "Open SSH for this runner", the last step still restores the SSH rule; if it printed a warning, run `terraform apply` as the runbook says.
