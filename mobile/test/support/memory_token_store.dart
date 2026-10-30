import 'package:skills_app/core/auth/token_store.dart';

/// A store that keeps everything in memory. For tests and previews only.
class MemoryTokenStore implements TokenStore {
  String? _access;
  String? _refresh;

  /// Forgets only the access token, as after an app restart (the refresh token survives).
  void clearAccessForRestart() => _access = null;

  @override
  String? get accessToken => _access;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    _access = accessToken;
    _refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }
}
