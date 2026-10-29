import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where the session tokens live.
///
/// The access token is kept in memory only (15 minutes, like the web). The refresh token is kept
/// in the Android Keystore through [SecureTokenStore]. Neither is ever logged or shown.
abstract class TokenStore {
  String? get accessToken;

  Future<String?> readRefreshToken();

  Future<void> save({
    required String accessToken,
    required String refreshToken,
  });

  Future<void> clear();
}

/// Keeps the refresh token in the platform keystore (`flutter_secure_storage`), never in
/// `shared_preferences`.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  static const _refreshKey = 'skills.refresh_token';

  final FlutterSecureStorage _storage;
  String? _access;

  @override
  String? get accessToken => _access;

  @override
  Future<String?> readRefreshToken() async {
    try {
      return await _storage.read(key: _refreshKey);
    } on Exception {
      // An unreadable keystore means "signed out"; the person logs in again.
      return null;
    }
  }

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    _access = accessToken;
    await _storage.write(key: _refreshKey, value: refreshToken);
  }

  @override
  Future<void> clear() async {
    _access = null;
    try {
      await _storage.delete(key: _refreshKey);
    } on Exception {
      // Nothing more can be done; the in-memory token is already gone.
    }
  }
}

/// A store that keeps everything in memory. For tests and previews only.
class MemoryTokenStore implements TokenStore {
  String? _access;
  String? _refresh;

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
