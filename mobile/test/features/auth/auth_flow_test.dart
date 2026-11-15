import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

void main() {
  group('welcome', () {
    testWidgets('offers joining and signing in, in the installation\'s words', (
      tester,
    ) async {
      await pumpApp(tester, words: churchWords);
      expect(find.byKey(const Key('member-join')), findsOneWidget);
      expect(find.byKey(const Key('member-sign-in')), findsOneWidget);
      expect(find.text('I belong to a home group'), findsOneWidget);
    });

    testWidgets('has no entry for the older account types or an admin', (
      tester,
    ) async {
      await pumpApp(tester, size: const Size(400, 1600));
      for (final key in [
        'login-freelancer',
        'login-workhost',
        'login-organisation',
        'register-freelancer',
        'register-workhost',
        'register-organisation',
        'login-admin',
      ]) {
        expect(find.byKey(Key(key)), findsNothing, reason: key);
      }
      expect(find.textContaining('Admin'), findsNothing);
    });
  });

  group('forgot password', () {
    testWidgets('always gives the same confirmation and sends only the email', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/forgot-password',
          FakeReply(202, {'status': 'accepted'}),
        ),
      );
      await tapKey(tester, 'member-sign-in');
      await tester.tap(find.text('Forgot your password?'));
      await tester.pumpAndSettle();
      await tapKey(tester, 'forgot-submit');
      expect(find.text('This field is required.'), findsOneWidget);
      expect(app.adapter.count('POST', '/auth/forgot-password'), 0);
      await typeInto(tester, 'Email', 'someone@example.test');
      await tapKey(tester, 'forgot-submit');
      expect(
        find.textContaining('If an account exists for that email'),
        findsOneWidget,
      );
      expect(app.adapter.seen.last.body, {'email': 'someone@example.test'});
    });
  });

  group('accessibility', () {
    testWidgets(
      'the welcome and sign-in screens work at text scale 2.0 on a small phone',
      (tester) async {
        await pumpApp(tester, size: const Size(320, 640), textScale: 2.0);
        expect(tester.takeException(), isNull);
        await tapKey(tester, 'member-sign-in');
        expect(tester.takeException(), isNull);
        await tester.scrollUntilVisible(
          find.byKey(const Key('member-login-submit')),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.byKey(const Key('member-login-submit')), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('tap targets are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpApp(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });
}
