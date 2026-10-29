import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/errors/error_messages.dart';
import 'package:skills_app/core/terminology/terms.dart';

ApiException error(
  String code, {
  int status = 400,
  int? retry,
  String message = 'server text',
}) => ApiException(
  status: status,
  code: code,
  message: message,
  retryAfterSeconds: retry,
);

void main() {
  const base = Terms({
    'organisation': 'Organisation',
    'freelancer': 'Freelancer',
  });
  const church = Terms({'organisation': 'Church', 'freelancer': 'Searcher'});

  test('a wrong password gives the same text as the web', () {
    expect(
      messageFor(error('invalid_credentials', status: 401), base),
      'Invalid email or password.',
    );
  });

  test('role words come from the terms', () {
    expect(
      messageFor(error('organisation_pending'), base),
      'This organisation is still waiting for admin approval.',
    );
    expect(
      messageFor(error('organisation_pending'), church),
      'This church is still waiting for admin approval.',
    );
    expect(
      messageFor(error('already_vouched'), church),
      'You already vouch for this searcher.',
    );
  });

  test('wait times are rounded up to whole minutes, at least one', () {
    expect(
      messageFor(error('too_many_attempts', status: 429, retry: 61), base),
      'Too many failed attempts. Try again in 2 minute(s).',
    );
    expect(
      messageFor(error('too_many_attempts', status: 429, retry: 5), base),
      'Too many failed attempts. Try again in 1 minute(s).',
    );
    expect(
      messageFor(error('too_many_attempts', status: 429), base),
      'Too many failed attempts. Try again in 1 minute(s).',
    );
    expect(
      messageFor(error('reveal_limit_reached', status: 429, retry: 600), base),
      'You have revealed many numbers recently. Try again in 10 minute(s).',
    );
  });

  test('network trouble has its own text', () {
    expect(
      messageFor(const ApiException.network(), base),
      'Cannot reach the server. Check your connection and try again.',
    );
  });

  test('an unknown code never shows the server text', () {
    final text = messageFor(
      error('something_new', message: 'secret internals'),
      base,
    );
    expect(text, 'Something went wrong. Please try again.');
    expect(text, isNot(contains('internals')));
  });

  test('a non-API error gives the generic text', () {
    expect(
      messageFor(StateError('boom'), base),
      'Something went wrong. Please try again.',
    );
  });

  test('texts do not talk about reloading a page', () {
    for (final code in [
      'not_found',
      'vouch_not_pending',
      'already_rated',
      'unknown_label',
    ]) {
      expect(
        messageFor(error(code), base).toLowerCase(),
        isNot(contains('reload')),
        reason: code,
      );
      expect(
        messageFor(error(code), base).toLowerCase(),
        isNot(contains('page')),
        reason: code,
      );
    }
  });
}
