import 'api_exception.dart';

/// Builds a value from a JSON object answered by the API. A body of the wrong shape (not an
/// object, a missing or mistyped field, an unknown value) becomes an [ApiException.badResponse]
/// instead of a raw cast error, so screens show the normal "something went wrong" text.
T parseResponse<T>(Object? data, T Function(Map<String, Object?> json) build) {
  if (data is! Map) throw const ApiException.badResponse();
  try {
    return build(Map<String, Object?>.from(data));
  } on TypeError {
    throw const ApiException.badResponse();
  } on FormatException {
    throw const ApiException.badResponse();
  }
}
