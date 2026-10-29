import '../api/api_client.dart';
import '../api/parse.dart';
import 'me.dart';
import 'token_store.dart';
import 'user_type.dart';

/// Login, logout and the current account. Passwords are passed through and never stored.
class AuthRepository {
  AuthRepository(this._api, this._tokens);

  final ApiClient _api;
  final TokenStore _tokens;

  /// Logs in as [type]. Throws `ApiException` (`invalid_credentials`, `too_many_attempts`,
  /// `organisation_pending`, ...).
  Future<Me> login({
    required String email,
    required String password,
    required UserType type,
  }) async {
    final data = await _api.post(
      '/auth/login',
      body: {'email': email, 'password': password, 'user_type': type.wire},
      auth: false,
    );
    final (access, refresh) = parseResponse(
      data,
      (json) =>
          (json['access_token'] as String, json['refresh_token'] as String),
    );
    await _tokens.save(accessToken: access, refreshToken: refresh);
    try {
      return await me();
    } catch (_) {
      // A login that cannot load the account is a failed login: do not leave a session behind.
      await _tokens.clear();
      rethrow;
    }
  }

  Future<Me> me() async => parseResponse(await _api.get('/me'), Me.fromJson);

  /// Opens a saved session after the app starts. Returns null when there is none (or it expired).
  Future<Me?> restoreSession() async {
    if (await _tokens.readRefreshToken() == null) return null;
    if (_tokens.accessToken == null && !await _api.refreshSession()) {
      return null;
    }
    return me();
  }

  /// Revokes the refresh token on the server (best effort) and forgets the tokens here.
  Future<void> logout() async {
    final refreshToken = await _tokens.readRefreshToken();
    try {
      if (refreshToken != null) {
        await _api.post(
          '/auth/logout',
          body: {'refresh_token': refreshToken},
          auth: false,
        );
      }
    } on Exception {
      // Offline or already revoked: the person is signed out on this phone either way.
    } finally {
      await _tokens.clear();
    }
  }
}
