import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/strings/app_text.dart';
import 'package:skills_app/core/terminology/terms.dart';

void main() {
  const church = AppText(
    Terms({
      'organisation': 'Church',
      'organisations': 'Churches',
      'workhost': 'Searcher',
      'freelancer': 'Provider',
    }),
  );

  test('fills a value', () {
    expect(church('dashboard.welcome', {'name': 'Pat'}), 'Welcome, Pat');
  });

  test(
    'a typed value that looks like a role word is shown exactly as typed',
    () {
      expect(
        church('dashboard.welcome', {
          'name': '{organisation} {Workhost} {a_freelancer}',
        }),
        'Welcome, {organisation} {Workhost} {a_freelancer}',
      );
    },
  );

  test('values do not substitute into each other', () {
    expect(
      church('dashboard.welcome', {'name': '{x}', 'x': 'boom'}),
      'Welcome, {x}',
    );
  });

  test('role words in the template still resolve', () {
    expect(church('register.organisation.title'), 'Create a church account');
  });

  test('an unknown key is a programming error', () {
    expect(() => church('no.such.key'), throwsStateError);
  });

  test('error gives the web wording with the role words filled in', () {
    expect(
      church.error(
        const ApiException(
          status: 403,
          code: 'organisation_pending',
          message: 'x',
        ),
      ),
      'This church is still waiting for admin approval.',
    );
    expect(
      church.error(const ApiException.network()),
      'Cannot reach the server. Check your connection and try again.',
    );
  });

  test('error never shows an unknown code or the server text', () {
    const unknown = ApiException(
      status: 500,
      code: 'surprise',
      message: 'internal detail',
    );
    expect(church.error(unknown), 'Something went wrong. Please try again.');
    expect(
      church.error(StateError('boom')),
      'Something went wrong. Please try again.',
    );
  });
}
