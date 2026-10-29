# Skills Android app

Flutter (Material 3) client for the Skills API. Plan: [docs/android/plan.md](../docs/android/plan.md); how to run on a device: [docs/android/environment.md](../docs/android/environment.md); web parity: [docs/android/parity.md](../docs/android/parity.md).

```bash
export PATH="$HOME/flutter/bin:$PATH"
cd mobile
flutter pub get
flutter devices                                   # the attached phone
flutter run --flavor demo -d <device> --dart-define=API_BASE_URL=https://<server>/api/v1
```

Checks (same as CI): `dart format --set-exit-if-changed .`, `flutter analyze`, `flutter test --coverage`.

The server address is a build setting, not a secret. No password, token, signing key or `google-services.json` is ever committed; CI supplies them (see `scripts/check-secrets.sh`).
