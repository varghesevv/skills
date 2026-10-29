import 'dart:async';

import 'package:dio/dio.dart';

import '../auth/token_store.dart';
import 'api_exception.dart';

/// The one place that talks to the API (`/api/v1`).
///
/// Behaviour matches `frontend/src/api/http.ts`: bearer token on every request except the
/// public ones, one refresh and retry on `401`, concurrent refreshes share one request, a
/// refresh token the server rejects is forgotten and [onSessionExpired] is called.
/// Nothing in here logs a request, a response or a token.
class ApiClient {
  ApiClient({
    required Dio dio,
    required TokenStore tokens,
    this.onSessionExpired,
    String appVersion = '',
  }) : _dio = dio, // ignore: prefer_initializing_formals (private fields, public named parameters)
       _tokens = tokens, // ignore: prefer_initializing_formals
       _appVersion = appVersion; // ignore: prefer_initializing_formals

  final Dio _dio;
  final TokenStore _tokens;
  final String _appVersion;

  /// Called when the refresh token is rejected, so the app can return to the login screen.
  final void Function()? onSessionExpired;

  Future<bool>? _refreshInFlight;

  /// A refresh that fails for these statuses means the token is no good (not a temporary
  /// problem). 429 and server errors keep the token so a later attempt can still work.
  static bool _tokenRejected(int status) =>
      status >= 400 && status < 500 && status != 429;

  Future<Object?> get(
    String path, {
    Map<String, Object?>? query,
    bool auth = true,
  }) => _request('GET', path, query: query, auth: auth);

  Future<Object?> post(String path, {Object? body, bool auth = true}) =>
      _request('POST', path, body: body, auth: auth);

  Future<Object?> put(String path, {Object? body}) =>
      _request('PUT', path, body: body);

  Future<Object?> patch(String path, {Object? body}) =>
      _request('PATCH', path, body: body);

  Future<Object?> delete(String path) => _request('DELETE', path);

  /// Trades the refresh token for new tokens. Concurrent callers share one request.
  Future<bool> refreshSession() {
    return _refreshInFlight ??= _exchangeRefreshToken().whenComplete(
      () => _refreshInFlight = null,
    );
  }

  Future<bool> _exchangeRefreshToken() async {
    final refreshToken = await _tokens.readRefreshToken();
    if (refreshToken == null) return false;
    final Response<Object?> response;
    try {
      response = await _send(
        'POST',
        '/auth/refresh',
        body: {'refresh_token': refreshToken},
      );
    } on ApiException {
      return false; // Network trouble: keep the token for a later attempt.
    }
    final status = response.statusCode ?? 0;
    if (status >= 200 && status < 300) {
      final data = response.data;
      if (data is Map &&
          data['access_token'] is String &&
          data['refresh_token'] is String) {
        await _tokens.save(
          accessToken: data['access_token'] as String,
          refreshToken: data['refresh_token'] as String,
        );
        return true;
      }
      return false;
    }
    if (_tokenRejected(status)) {
      await _tokens.clear();
      // Once per expiry: this runs inside the shared refresh, not once per waiting request.
      onSessionExpired?.call();
    }
    return false;
  }

  Future<Object?> _request(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    bool auth = true,
  }) async {
    var response = await _send(
      method,
      path,
      body: body,
      query: query,
      token: auth,
    );
    if (response.statusCode == 401 &&
        auth &&
        await _tokens.readRefreshToken() != null) {
      if (await refreshSession()) {
        response = await _send(
          method,
          path,
          body: body,
          query: query,
          token: auth,
        );
      }
    }
    final status = response.statusCode ?? 0;
    if (status < 200 || status >= 300) throw _toException(response);
    return status == 204 ? null : response.data;
  }

  Future<Response<Object?>> _send(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    bool token = false,
  }) async {
    final headers = <String, Object>{
      'Accept': 'application/json',
      'X-App-Platform': 'android',
      if (_appVersion.isNotEmpty) 'X-App-Version': _appVersion,
      if (token && _tokens.accessToken != null)
        'Authorization': 'Bearer ${_tokens.accessToken}',
    };
    try {
      return await _dio.request<Object?>(
        path,
        data: body,
        queryParameters: query,
        options: Options(
          method: method,
          headers: headers,
          // Statuses are handled here, so a 4xx never turns into a thrown DioException.
          validateStatus: (_) => true,
          responseType: ResponseType.json,
        ),
      );
    } on DioException {
      throw const ApiException.network();
    }
  }

  ApiException _toException(Response<Object?> response) {
    var code = 'error';
    var message = 'Request failed with status ${response.statusCode}';
    var details = <String, Object?>{};
    final data = response.data;
    if (data is Map && data['error'] is Map) {
      final error = data['error'] as Map;
      if (error['code'] is String) code = error['code'] as String;
      if (error['message'] is String) message = error['message'] as String;
      if (error['details'] is Map) {
        details = Map<String, Object?>.from(error['details'] as Map);
      }
    }
    final retry = int.tryParse(response.headers.value('retry-after') ?? '');
    return ApiException(
      status: response.statusCode ?? 0,
      code: code,
      message: message,
      details: details,
      retryAfterSeconds: retry != null && retry > 0 ? retry : null,
    );
  }
}
