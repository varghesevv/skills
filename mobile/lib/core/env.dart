/// Build-time settings, passed with `--dart-define`. None of them is a secret.
class Env {
  const Env._();

  /// Address of the API server including the `/api/v1` path, for example
  /// `https://demo.example.org/api/v1`. Required: an empty value is a build mistake.
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  /// The app version sent as `X-App-Version` (`X.Y.Z`, optional `+build`). Required in release
  /// builds: without it the "please update" check could never run.
  static const appVersion = String.fromEnvironment('APP_VERSION');

  /// `demo` or `prod`; matches the Gradle product flavor.
  static const flavor = String.fromEnvironment('FLAVOR', defaultValue: 'demo');

  static final _version = RegExp(r'^\d+\.\d+\.\d+(\+\d+)?$');

  /// Names of the build settings that are missing or wrong. Empty when the build is configured.
  /// Release builds refuse to start with a non-empty list; debug and test builds may leave the
  /// settings out.
  static List<String> problems({String? apiBase, String? version}) {
    final base = apiBase ?? apiBaseUrl;
    final appVer = version ?? appVersion;
    return [
      if (base.isEmpty) 'API_BASE_URL',
      if (!_version.hasMatch(appVer)) 'APP_VERSION',
    ];
  }
}
