# Android application: development environment

Status: phase 0 result, checked on 2026-10-29 on the development host (the machine VS Code connects to over Remote-SSH). Checks are those of [plan](plan.md) section 2. No secrets, device serials or network addresses are recorded here.

## 1. Findings

| Check | Result | Verdict |
|---|---|---|
| CPU and OS | x86_64, Ubuntu 26.04 LTS, kernel 6.6 (NAS host, probably a container) | Good: the Android SDK tools work. |
| Java | OpenJDK 17.0.20 (`/usr/bin/java`) | Good (JDK 17 or 21 needed). |
| Flutter | 3.47.8 stable (Dart 3.13.7) in `~/flutter`; **not on `PATH`** | Works when `~/flutter/bin` is on `PATH`. `flutter doctor -v`: no issues. |
| Android SDK | `ANDROID_HOME=~/android-sdk`; platform-tools 37.0.1, platforms android-34 and android-36, build-tools 28.0.3, 34.0.0 and 36.0.0, NDK r28c; all licences accepted | Good. Build-tools 36 and the NDK were added by Flutter on the first build (user-level, inside the SDK folder). |
| Emulator | No `/dev/kvm`, no `emulator` package, no system images | **Not available.** Do not plan on an emulator on this host. |
| Real phone | One Pixel 6 Pro, Android 16 (API 36), arm64, connected over **wireless debugging**; `adb devices` lists it twice (a paired mDNS entry and an IP:port entry) | Good. Option 1 of plan section 2. |
| Disk | About 3.9 TB free | Good. |
| RAM | 31 GB total, about 6 GB available at the time (other workloads on the host); 60 GB swap; 8 cores | Good enough. Gradle daemon is the main consumer. |
| Other tools | git 2.53, Python 3.14, Docker 29 present; **Node is not installed**; `sudo` needs a password | See section 4. |
| Hello-world | `flutter create` + `flutter build apk --debug` succeeded in the scratch area (first build 7 min because Gradle, the NDK and build-tools were downloaded; `~/.gradle` is now 2.6 GB). Not installed on the phone. | Phase 0 acceptance met for building. |

## 2. Chosen way of running the app

**Option 1 of the plan: physical phone with wireless debugging**, driven from this host. Flutter sees the phone as a device, so `flutter run -d <device>` gives hot reload through VS Code. Integration tests that need a device run on that phone. There is no emulator; CI builds the release artifacts on GitHub-hosted runners, and emulator smoke tests (plan section 8, "Release") run in CI only if a hosted runner with KVM is used. That is a phase 7 decision.

Wireless debugging pairing expires when the phone changes network or reboots; re-pair with `adb pair <ip:port>` then `adb connect`.

## 3. Setup used (user-level only, nothing system-wide)

```bash
# add to ~/.bashrc (not done automatically)
export PATH="$HOME/flutter/bin:$PATH"
export ANDROID_HOME="$HOME/android-sdk"      # already present
```

Gradle and pub caches live in `~/.gradle` and `~/.pub-cache`. The server address is passed with `--dart-define=API_BASE_URL=...` and is not a secret.

## 4. Things the owner must do

1. Put `~/flutter/bin` on `PATH` in `~/.bashrc` (or tell Claude to do it), and install the VS Code Flutter and Dart extensions on the remote.
2. Keep the phone awake, on the same network as this host, with wireless debugging on, while testing. Phase 6 acceptance needs a **second device** (a second phone, or a CI emulator) for two-sided chat tests.
3. Node.js is only needed when the web front end changes (`npm` scripts). If a web PR is needed, install it user-level (for example with nvm) or confirm it may be installed; until then web checks cannot be run here.
4. Answer Q-A1 (app name, application ID) before the first signed build; local builds use `com.example.skills.dev`.
5. Later: Firebase project (free) and Google Play Console account; neither is needed before phase 6 and phase 7.
