/// An error answered by the API (or a network failure), in the API's error envelope shape:
/// `{ "error": { "code", "message", "details" } }`. Mirrors `ApiError` in the web client.
///
/// The [message] is the server's text and is for developers; people see the text chosen by
/// `messageFor` from the [code]. It never holds anything the person typed.
class ApiException implements Exception {
  const ApiException({
    required this.status,
    required this.code,
    required this.message,
    this.details = const {},
    this.retryAfterSeconds,
  });

  /// A request that never got an answer (no connection, timeout). Status 0, like the web.
  const ApiException.network()
    : status = 0,
      code = 'network_error',
      message = 'Network error',
      details = const {},
      retryAfterSeconds = null;

  /// The server answered, but not in the shape this app version expects.
  const ApiException.badResponse()
    : status = 0,
      code = 'bad_response',
      message = 'Unexpected response',
      details = const {},
      retryAfterSeconds = null;

  final int status;
  final String code;
  final String message;
  final Map<String, Object?> details;

  /// Seconds from the `Retry-After` header, when the server sent one.
  final int? retryAfterSeconds;

  @override
  String toString() => 'ApiException($status, $code)';
}
