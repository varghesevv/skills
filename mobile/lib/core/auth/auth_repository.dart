import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../api/parse.dart';
import 'person_me.dart';
import 'token_store.dart';

/// Login, logout and the current account. Passwords are passed through and never stored.
class AuthRepository {
  AuthRepository(this._api, this._tokens);

  final ApiClient _api;
  final TokenStore _tokens;

  /// Logs in. Throws `ApiException` (`invalid_credentials`, `too_many_attempts`, ...).
  Future<PersonMe> loginPerson({
    required String email,
    required String password,
  }) async {
    final data = await _api.post(
      '/auth/login',
      body: {'email': email, 'password': password},
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
      await _tokens.clear();
      rethrow;
    }
  }

  /// The signed-in person. An answer that is not a person (an account of the older kind, which
  /// the server no longer serves) is a bad response.
  Future<PersonMe> me() async => parseResponse(await _api.get('/me'), (json) {
    if (json['user_type'] != 'person') {
      throw const FormatException('Not a person');
    }
    return PersonMe.fromJson(json);
  });

  /// Opens a saved session after the app starts. Returns null when there is none (or it expired).
  Future<PersonMe?> restoreSession() async {
    if (await _tokens.readRefreshToken() == null) return null;
    if (_tokens.accessToken == null && !await _api.refreshSession()) {
      return null;
    }
    try {
      return await me();
    } on ApiException catch (error) {
      // A session of an account of the older kind cannot be used any more: end it (the refresh
      // token is revoked on the server, best effort) so the app opens at the welcome screen
      // instead of failing at every start.
      if (error.code != 'bad_response') rethrow;
      await logout();
      return null;
    }
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
