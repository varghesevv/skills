import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../api/parse.dart';
import 'person_me.dart';
import 'token_store.dart';

/// `GET /me` answered with an account of the older kind (a freelancer, work host or
/// organisation). The app has no screens for it. It is not an [ApiException]: only this exact
/// answer ends a saved session; any other unreadable answer keeps it.
class OlderAccountException implements Exception {
  const OlderAccountException();

  @override
  String toString() => 'OlderAccountException';
}

const _olderAccountTypes = {'freelancer', 'workhost', 'organisation'};

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
    } on OlderAccountException {
      // No screens for it: the same as any answer the app cannot use.
      await _tokens.clear();
      throw const ApiException.badResponse();
    } catch (_) {
      await _tokens.clear();
      rethrow;
    }
  }

  /// The signed-in person. Throws [OlderAccountException] for an account of the older kind, and
  /// an `ApiException` (`bad_response`) for any other answer the app cannot read.
  Future<PersonMe> me() async => parseResponse(await _api.get('/me'), (json) {
    if (_olderAccountTypes.contains(json['user_type'])) {
      throw const OlderAccountException();
    }
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
    } on OlderAccountException {
      // A session of an account of the older kind cannot be used any more: end it (the refresh
      // token is revoked on the server, best effort) so the app opens at the welcome screen
      // instead of failing at every start. Any other failure keeps the saved session.
      await logout();
      return null;
    }
  }

  /// Replaces the password, giving the current one. Every other session ends on the server; the
  /// answer holds new tokens for this one, saved here. Returns the person as they now are.
  Future<PersonMe> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final data = await _api.post(
      '/auth/change-password',
      body: {'current_password': currentPassword, 'new_password': newPassword},
    );
    final (access, refresh) = parseResponse(
      data,
      (json) =>
          (json['access_token'] as String, json['refresh_token'] as String),
    );
    await _tokens.save(accessToken: access, refreshToken: refresh);
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
