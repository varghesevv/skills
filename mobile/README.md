# Skills Android app

Flutter (Material 3) client for the Skills API. Plan: [docs/android/plan.md](../docs/android/plan.md). How to run on a device (`docs/android/environment.md`) and the web parity table (`docs/android/parity.md`) are added by the docs pull request.

```bash
export PATH="$HOME/flutter/bin:$PATH"
cd mobile
flutter pub get
flutter devices                                   # the attached phone
flutter run --flavor demo -d <device> --dart-define=API_BASE_URL=https://<server>/api/v1
```

Checks (same as CI): `dart format --set-exit-if-changed .`, `flutter analyze`, `flutter test --coverage`.

The server address is a build setting, not a secret. No password, token, signing key or `google-services.json` is ever committed; CI supplies them (see `scripts/check-secrets.sh`).

## Build settings

| Setting (`--dart-define=...`) | Needed | Meaning |
|---|---|---|
| `API_BASE_URL` | release builds | Server address including `/api/v1`. Not a secret. |
| `APP_VERSION` | release builds | `X.Y.Z` or `X.Y.Z+N`. Sent as `X-App-Version` and compared with the server's minimum version for the "please update" screen. |

A **release** build made without them (or with a malformed version) shows a "this build is not configured" screen that names the missing settings, instead of running with the update check silently off. Debug builds and tests may leave them out. The release workflow passes both from the app version in `pubspec.yaml`.
