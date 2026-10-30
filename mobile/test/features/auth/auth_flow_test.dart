import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

void main() {
  group('welcome', () {
    testWidgets('shows the default role words', (tester) async {
      await pumpApp(tester);
      expect(find.text('I am a freelancer'), findsOneWidget);
      expect(find.text('I represent an organisation'), findsOneWidget);
    });

    testWidgets('shows the words the server sends for the church profile', (
      tester,
    ) async {
      await pumpApp(tester, words: churchWords);
      expect(find.text('I am a searcher'), findsOneWidget);
      expect(find.text('I represent a church'), findsOneWidget);
      expect(find.textContaining('Freelancer'), findsNothing);
      expect(find.textContaining('Organisation'), findsNothing);
    });

    testWidgets('has no admin entry', (tester) async {
      await pumpApp(tester);
      expect(find.byKey(const Key('login-admin')), findsNothing);
      expect(find.textContaining('Admin'), findsNothing);
    });
  });

  group('login', () {
    testWidgets('validates before asking the server', (tester) async {
      final app = await pumpApp(tester);
      await tapKey(tester, 'login-workhost');
      await tapKey(tester, 'login-submit');
      expect(find.text('Enter a valid email address.'), findsNothing);
      expect(find.text('This field is required.'), findsNWidgets(2));
      expect(app.adapter.count('POST', '/auth/login'), 0);
    });

    testWidgets('logs in as the chosen role and shows the dashboard', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter
          ..reply(
            'POST',
            '/auth/login',
            FakeReply(200, tokens(fresh('a'), fresh('r'))),
          )
          ..reply('GET', '/me', FakeReply(200, meJson('workhost'))),
      );
      await tapKey(tester, 'login-workhost');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Password', password);
      await tapKey(tester, 'login-submit');
      expect(find.text('Welcome, Pat Example'), findsOneWidget);
      expect(find.text('Work host'), findsOneWidget);
      final login = app.adapter.seen.firstWhere((r) => r.path == '/auth/login');
      expect(login.body, {
        'email': 'person@example.test',
        'password': password,
        'user_type': 'workhost',
      });
    });

    testWidgets('a wrong password shows the web wording and clears the field', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/login',
          FakeReply(401, apiError('invalid_credentials')),
        ),
      );
      await tapKey(tester, 'login-freelancer');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Password', fresh('pw'));
      await tapKey(tester, 'login-submit');
      expect(find.text('Invalid email or password.'), findsOneWidget);
      expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, 'Password'))
            .controller!
            .text,
        isEmpty,
      );
    });

    testWidgets('too many attempts shows the wait in minutes', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/login',
          FakeReply(429, apiError('too_many_attempts'), const {
            'retry-after': ['600'],
          }),
        ),
      );
      await tapKey(tester, 'login-freelancer');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Password', fresh('pw'));
      await tapKey(tester, 'login-submit');
      expect(
        find.text('Too many failed attempts. Try again in 10 minute(s).'),
        findsOneWidget,
      );
    });

    testWidgets(
      'an organisation waiting for approval gets the church wording',
      (tester) async {
        await pumpApp(
          tester,
          words: churchWords,
          arrange: (adapter, store) => adapter.reply(
            'POST',
            '/auth/login',
            FakeReply(403, apiError('organisation_pending')),
          ),
        );
        await tapKey(tester, 'login-organisation');
        expect(
          find.textContaining(
            'A new church can log in once an admin has approved it.',
          ),
          findsOneWidget,
        );
        await typeInto(tester, 'Email', 'person@example.test');
        await typeInto(tester, 'Password', fresh('pw'));
        await tapKey(tester, 'login-submit');
        expect(
          find.text('This church is still waiting for admin approval.'),
          findsOneWidget,
        );
      },
    );

    testWidgets('can show and hide the password with a labelled button', (
      tester,
    ) async {
      await pumpApp(tester);
      await tapKey(tester, 'login-freelancer');
      expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, 'Password'))
            .obscureText,
        isTrue,
      );
      await tester.tap(find.byTooltip('Show password'));
      await tester.pump();
      expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, 'Password'))
            .obscureText,
        isFalse,
      );
      expect(find.byTooltip('Hide password'), findsOneWidget);
    });
  });

  group('register', () {
    testWidgets('checks the fields and shows the rules', (tester) async {
      final app = await pumpApp(tester);
      await tapKey(tester, 'register-workhost');
      await tapKey(tester, 'register-submit');
      expect(
        find.text('Enter your name (2 to 200 characters).'),
        findsOneWidget,
      );
      expect(find.text('Enter a valid email address.'), findsNothing);
      expect(
        find.text('Enter 7 to 15 digits, optionally starting with +.'),
        findsOneWidget,
      );
      expect(find.text('Use at least 10 characters.'), findsOneWidget);
      expect(
        app.adapter.seen.where((r) => r.path.startsWith('/auth/register')),
        isEmpty,
      );
    });

    testWidgets('a freelancer is created with empty optional fields as null', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/register/freelancer',
          FakeReply(201, {
            'id': 'u1',
            'user_type': 'freelancer',
            'email': 'p@e.test',
            'approval_status': null,
          }),
        ),
      );
      await tapKey(tester, 'register-freelancer');
      await typeInto(tester, 'Full name', 'Pat Example');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Mobile number', '+971 50-123 4567');
      await typeInto(tester, 'Password', '${password}xxxxxxxxxx');
      await tapKey(tester, 'register-submit');
      expect(find.text('Account created'), findsOneWidget);
      expect(find.text('You can now log in.'), findsOneWidget);
      final body =
          app.adapter.seen
                  .firstWhere((r) => r.path == '/auth/register/freelancer')
                  .body!
              as Map;
      expect(body['mobile_number'], '+971501234567');
      expect(body['nationality'], isNull);
      expect(body['primary_language'], isNull);
      expect(body['whatsapp_availability'], false);
      expect(body.containsKey('org_name'), isFalse);
    });

    testWidgets(
      'an organisation is told it waits for approval, in the church words',
      (tester) async {
        await pumpApp(
          tester,
          words: churchWords,
          arrange: (adapter, store) => adapter.reply(
            'POST',
            '/auth/register/organisation',
            FakeReply(201, {
              'id': 'u1',
              'user_type': 'organisation',
              'email': 'p@e.test',
              'approval_status': 'pending',
            }),
          ),
        );
        await tapKey(tester, 'register-organisation');
        await typeInto(tester, 'Church Name', 'Example Church');
        await typeInto(tester, 'Email', 'person@example.test');
        await typeInto(tester, 'Mobile number', '5551234');
        await typeInto(tester, 'Password', fresh('pw') * 2);
        await tapKey(tester, 'register-submit');
        expect(
          find.text(
            'Your church is waiting for admin approval. You can log in after it is approved.',
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets('an email already in use is shown at the email field', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/register/workhost',
          FakeReply(409, apiError('email_taken')),
        ),
      );
      await tapKey(tester, 'register-workhost');
      await typeInto(tester, 'Full name', 'Pat Example');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Mobile number', '5551234');
      await typeInto(tester, 'Password', fresh('pw') * 2);
      await tapKey(tester, 'register-submit');
      expect(
        find.text('An account with this email already exists.'),
        findsNWidgets(2),
      ); // banner + field
    });

    testWidgets('server field errors line up with the fields', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/register/workhost',
          FakeReply(422, {
            'error': {
              'code': 'validation_error',
              'message': 'm',
              'details': {
                'fields': [
                  {
                    'field': 'mobile_number',
                    'message': 'Not a valid number for this country.',
                  },
                ],
              },
            },
          }),
        ),
      );
      await tapKey(tester, 'register-workhost');
      await typeInto(tester, 'Full name', 'Pat Example');
      await typeInto(tester, 'Email', 'person@example.test');
      await typeInto(tester, 'Mobile number', '5551234');
      await typeInto(tester, 'Password', fresh('pw') * 2);
      await tapKey(tester, 'register-submit');
      expect(find.text('Not a valid number for this country.'), findsOneWidget);
      expect(
        find.text('Please correct the highlighted fields.'),
        findsOneWidget,
      );
    });
  });

  group('forgot password', () {
    testWidgets('always gives the same confirmation', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/forgot-password',
          FakeReply(202, {'status': 'accepted'}),
        ),
      );
      await tapKey(tester, 'login-freelancer');
      await tester.tap(find.text('Forgot your password?'));
      await tester.pumpAndSettle();
      await tapKey(tester, 'forgot-submit');
      expect(find.text('Enter a valid email address.'), findsNothing);
      expect(find.text('This field is required.'), findsOneWidget);
      await typeInto(tester, 'Email', 'someone@example.test');
      await tapKey(tester, 'forgot-submit');
      expect(
        find.textContaining('If an account exists for that email'),
        findsOneWidget,
      );
      expect(app.adapter.seen.last.body, {
        'email': 'someone@example.test',
        'user_type': 'freelancer',
      });
    });
  });

  group('accessibility', () {
    testWidgets('the login screen works at text scale 2.0 on a small phone', (
      tester,
    ) async {
      await pumpApp(tester, size: const Size(320, 640), textScale: 2.0);
      await tapKey(tester, 'login-organisation');
      expect(tester.takeException(), isNull);
      // The form is a scrolling list: the button is reachable by scrolling, nothing is clipped.
      await tester.scrollUntilVisible(
        find.byKey(const Key('login-submit')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.byKey(const Key('login-submit')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('tap targets are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpApp(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });
}
