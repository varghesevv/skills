import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// One request the code under test made.
class SeenRequest {
  SeenRequest(this.method, this.path, this.headers, this.body);

  final String method;
  final String path;
  final Map<String, Object?> headers;
  final Object? body;

  String? get authorization => headers['Authorization'] as String?;
}

/// A reply for the next request. [delay] lets a test hold a response to prove single-flight.
class FakeReply {
  FakeReply(this.status, [this.json, this.headers = const {}, this.delay]);

  final int status;
  final Object? json;
  final Map<String, List<String>> headers;
  final Future<void>? delay;
}

/// A stand-in for the network. Replies are served in order per `METHOD path`; nothing real is
/// contacted and no real credentials are used.
class FakeAdapter implements HttpClientAdapter {
  final seen = <SeenRequest>[];
  final _replies = <String, List<FakeReply>>{};
  bool failWithNetworkError = false;

  void reply(String method, String path, FakeReply reply) {
    (_replies['$method $path'] ??= []).add(reply);
  }

  /// Replaces whatever was queued for this request with one reply (for example "the server is
  /// back" after an error).
  void setReply(String method, String path, FakeReply reply) {
    _replies['$method $path'] = [reply];
  }

  int count(String method, String path) =>
      seen.where((r) => r.method == method && r.path == path).length;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    seen.add(
      SeenRequest(
        options.method,
        options.path,
        Map.of(options.headers),
        options.data,
      ),
    );
    if (failWithNetworkError) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline',
      );
    }
    final queue = _replies['${options.method} ${options.path}'];
    if (queue == null || queue.isEmpty) {
      return ResponseBody.fromString(
        '{}',
        404,
        headers: {
          Headers.contentTypeHeader: ['application/json'],
        },
      );
    }
    final next = queue.length > 1 ? queue.removeAt(0) : queue.first;
    if (next.delay != null) await next.delay;
    return ResponseBody.fromString(
      next.json == null ? '' : jsonEncode(next.json),
      next.status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
        ...next.headers,
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// The API's error envelope.
Map<String, Object?> apiError(String code, [String message = 'message']) => {
  'error': {'code': code, 'message': message, 'details': <String, Object?>{}},
};

Map<String, Object?> tokens(String access, String refresh) => {
  'access_token': access,
  'refresh_token': refresh,
  'expires_in': 900,
};

var _counter = 0;

/// A value that is different in every call and every run, for passwords and tokens in tests.
String fresh(String label) =>
    '$label-${DateTime.now().microsecondsSinceEpoch}-${_counter++}';
