# ADR-0015: Flutter for the mobile apps

- Status: Proposed
- Date: 2026-10-29
- Deciders: Project owner

## Context

The freelancer, work host and organisation features of the web application are wanted on phones,
Android first, with the iPhone possible later ([android/understanding.md](../android/understanding.md),
[mobile-app-plan.md](../mobile-app-plan.md)). The API is already usable by native clients
([ADR-0004](0004-stateless-token-auth-for-web-and-mobile.md)). The team is small and the development
host is a Linux server reached over Remote-SSH with a physical phone for testing
([android/environment.md](../android/environment.md)).

## Decision

Build one app in **Flutter** (Dart, Material 3) in the `mobile/` folder of this repository
([ADR-0007](0007-monorepo.md)), using the existing `/api/v1`. Android is built and released first.

## Alternatives considered

- Native Kotlin (Jetpack Compose): best Android fit, but a second code base and no iPhone reuse.
- React Native: shares language with the web front end, but the web code is not reusable as is, and
  the toolchain adds Node and native bridges to maintain.
- Progressive web app only: no push when closed on all devices, no store presence, weaker fit for the
  dialler and secure token storage.

## Consequences

- One code base for Android and, later, iOS. Planned: a mobile release train separate from the web
  (a release-please package `mobile`, decision 2 in [mobile-app-plan.md](../mobile-app-plan.md)).
- A Dart toolchain joins the repository: `flutter analyze`, `dart format`, `flutter test` run in
  `ci-mobile`. Planned (backend item B7): models are generated from an exported, CI-checked OpenAPI
  file so the app cannot drift from the API.
- Tokens are kept in the platform keystore through `flutter_secure_storage`; server addresses are
  build settings, signing and Firebase files are CI secrets and never committed
  ([ADR-0011](0011-secrets-from-environment-only.md)).
