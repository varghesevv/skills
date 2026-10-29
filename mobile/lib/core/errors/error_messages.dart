import '../api/api_exception.dart';
import '../terminology/terms.dart';

/// A message safe to show a person, chosen from the error code. Same texts as the web
/// (`frontend/src/shared/errors.ts` and `i18n`). Never includes anything the person typed or
/// the server's own message. [terms] resolves `{organisation}` style words.
String messageFor(Object error, Terms terms) {
  if (error is ApiException) {
    final text = _byCode(error);
    if (text != null) return terms.apply(text);
  }
  return _generic;
}

const _generic = 'Something went wrong. Please try again.';

int _minutes(ApiException error) =>
    ((error.retryAfterSeconds ?? 60) / 60).ceil().clamp(1, 1 << 30);

String? _byCode(ApiException e) {
  switch (e.code) {
    case 'invalid_credentials':
      return 'Invalid email or password.';
    case 'organisation_pending':
      return 'This {organisation} is still waiting for admin approval.';
    case 'organisation_rejected':
      return 'This {organisation} was not approved.';
    case 'too_many_attempts':
      return 'Too many failed attempts. Try again in ${_minutes(e)} minute(s).';
    case 'reveal_limit_reached':
      return 'You have revealed many numbers recently. Try again in ${_minutes(e)} minute(s).';
    case 'email_taken':
      return 'An account with this email already exists.';
    case 'invalid_reset_token':
      return 'This reset link is invalid or has expired. Request a new one.';
    case 'network_error':
      return 'Cannot reach the server. Check your connection and try again.';
    case 'service_unavailable':
      return 'The service is temporarily unavailable. Please try again soon.';
    case 'validation_error':
      return 'Please correct the highlighted fields.';
    case 'unavailability_overlaps':
      return 'This period overlaps one you already have.';
    case 'unknown_label':
    case 'invalid_level':
    case 'duplicate_label':
    case 'level_not_selectable':
      return 'One of the selected labels is no longer available. Reload and try again.';
    case 'not_found':
      return 'That item no longer exists. Reload the page.';
    case 'vouch_not_pending':
      return 'This vouch was already decided. Reload the page.';
    case 'organisation_not_approved':
      return 'Your {organisation} must be approved by an admin first.';
    case 'already_vouched':
      return 'You already vouch for this {freelancer}.';
    case 'already_rated':
      return 'You already rated this {freelancer}. Reload the page to change your rating.';
    case 'forbidden':
      return 'You are not allowed to do this.';
    case 'currency_required':
      return 'A highest rate needs a currency.';
    case 'availability_range':
      return 'Give both dates, with the start before the end.';
    case 'report_error':
    case 'report_window':
      return 'The report could not run for these dates. Check the date range.';
  }
  return null;
}

/// Field-level messages from a `validation_error` answer, keyed by API field name. The server
/// texts describe the rule only and never include what the person typed.
Map<String, String> serverFieldErrors(Object error) {
  if (error is! ApiException || error.code != 'validation_error') {
    return const {};
  }
  final fields = error.details['fields'];
  if (fields is! List) return const {};
  final result = <String, String>{};
  for (final item in fields) {
    if (item is Map && item['field'] is String && item['message'] is String) {
      result.putIfAbsent(
        item['field'] as String,
        () => item['message'] as String,
      );
    }
  }
  return result;
}
