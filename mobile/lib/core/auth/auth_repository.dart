import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../api/parse.dart';
import 'account.dart';
import 'me.dart';
import 'person_me.dart';
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
      final account = await me();
      if (account is! Me) throw const ApiException.badResponse();
      return account;
    } catch (_) {
      // A login that cannot load the account is a failed login: do not leave a session behind.
      await _tokens.clear();
      rethrow;
    }
  }

  /// The one login of the church trust model: no account type is sent.
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
      final account = await me();
      if (account is! PersonMe) throw const ApiException.badResponse();
      return account;
    } catch (_) {
      await _tokens.clear();
      rethrow;
    }
  }

  /// The signed-in account: a person of the church trust model, or an older account.
  Future<Account> me() async => parseResponse(
    await _api.get('/me'),
    (json) => json['user_type'] == 'person'
        ? PersonMe.fromJson(json)
        : Me.fromJson(json),
  );

  /// Opens a saved session after the app starts. Returns null when there is none (or it expired).
  Future<Account?> restoreSession() async {
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
