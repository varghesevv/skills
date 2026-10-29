import '../api/api_client.dart';
import '../api/parse.dart';
import 'terms.dart';

/// The public configuration of the installation (`GET /api/v1/app/config`, no login needed).
class AppConfig {
  const AppConfig({
    required this.profile,
    required this.terms,
    required this.minVersion,
    required this.latestVersion,
  });

  factory AppConfig.fromJson(Map<String, Object?> json) {
    final terminology = json['terminology'] as Map<String, Object?>;
    final app = json['app'] as Map<String, Object?>;
    return AppConfig(
      profile: terminology['profile'] as String,
      terms: Terms(Map<String, String>.from(terminology['terms'] as Map)),
      minVersion: app['min_version'] as String,
      latestVersion: app['latest_version'] as String,
    );
  }

  final String profile;
  final Terms terms;
  final String minVersion;
  final String latestVersion;

  /// True when [version] (`X.Y.Z`, optional `+build`) is older than the minimum the server asks for.
  bool requiresUpdate(String version) =>
      compareVersions(version, minVersion) < 0;

  /// True when a newer version than [version] exists.
  bool updateAvailable(String version) =>
      compareVersions(version, latestVersion) < 0;
}

/// Compares `X.Y.Z` versions as numbers (so 1.10.0 is newer than 1.9.0). A `+build` suffix is
/// ignored. A value that is not a version compares as 0.0.0, which never blocks anyone.
int compareVersions(String a, String b) {
  final left = _parts(a);
  final right = _parts(b);
  for (var i = 0; i < 3; i++) {
    if (left[i] != right[i]) return left[i].compareTo(right[i]);
  }
  return 0;
}

List<int> _parts(String version) {
  final core = version.split('+').first.split('.');
  return List.generate(
    3,
    (i) => i < core.length ? int.tryParse(core[i]) ?? 0 : 0,
  );
}

class AppConfigRepository {
  AppConfigRepository(this._api);

  final ApiClient _api;

  Future<AppConfig> fetch() async {
    final data = await _api.get('/app/config', auth: false);
    return parseResponse(data, AppConfig.fromJson);
  }
}
