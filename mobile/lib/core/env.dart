/// Build-time settings, passed with `--dart-define`. None of them is a secret.
class Env {
  const Env._();

  /// Address of the API server including the `/api/v1` path, for example
  /// `https://demo.example.org/api/v1`. Required: an empty value is a build mistake.
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  /// The app version sent as `X-App-Version` (`X.Y.Z`); set by the release build.
  static const appVersion = String.fromEnvironment('APP_VERSION');

  /// `demo` or `prod`; matches the Gradle product flavor.
  static const flavor = String.fromEnvironment('FLAVOR', defaultValue: 'demo');
}
