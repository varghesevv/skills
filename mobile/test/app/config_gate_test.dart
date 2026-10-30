import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/strings/bootstrap_strings.dart';

import '../support/fake_api.dart';
import '../support/test_app.dart';

void main() {
  testWidgets(
    'shows no role word until the config has loaded, and retries on failure',
    (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.failWithNetworkError = true,
      );
      expect(
        find.text(
          'Cannot reach the server. Check your connection and try again.',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Freelancer'), findsNothing);
      expect(find.textContaining('freelancer'), findsNothing);
      // The connection comes back.
      app.adapter.failWithNetworkError = false;
      app.adapter.reply('GET', '/app/config', FakeReply(200, configJson()));
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('I am a freelancer'), findsOneWidget);
    },
  );

  testWidgets('blocks the app when the server asks for a newer version', (
    tester,
  ) async {
    await pumpApp(tester, minVersion: '2.0.0', appVersion: '1.9.0');
    expect(find.text('Please update the app'), findsOneWidget);
    expect(find.textContaining('too old'), findsOneWidget);
    expect(find.text('I am a freelancer'), findsNothing);
  });

  testWidgets('lets the app run when its version is at least the minimum', (
    tester,
  ) async {
    await pumpApp(tester, minVersion: '1.10.0', appVersion: '1.10.0+7');
    expect(find.text('Please update the app'), findsNothing);
    expect(find.text('I am a freelancer'), findsOneWidget);
  });

  testWidgets('a debug run without a version is never blocked', (tester) async {
    await pumpApp(tester, minVersion: '9.0.0', appVersion: '');
    expect(find.text('I am a freelancer'), findsOneWidget);
  });

  testWidgets(
    'a server without the config endpoint gets a clear message, not "item no longer exists"',
    (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.setReply(
          'GET',
          '/app/config',
          FakeReply(404, apiError('not_found')),
        ),
      );
      expect(
        find.textContaining('server address may be wrong'),
        findsOneWidget,
      );
      expect(find.textContaining('no longer exists'), findsNothing);
      expect(find.text('Try again'), findsOneWidget);
    },
  );

  testWidgets('an unexpected config answer gets the same message', (
    tester,
  ) async {
    await pumpApp(
      tester,
      arrange: (adapter, store) => adapter.setReply(
        'GET',
        '/app/config',
        FakeReply(200, {'terminology': 'oops'}),
      ),
    );
    expect(find.textContaining('server address may be wrong'), findsOneWidget);
  });

  testWidgets('trying again works once the server is updated', (tester) async {
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) => adapter.setReply(
        'GET',
        '/app/config',
        FakeReply(404, apiError('not_found')),
      ),
    );
    app.adapter.setReply('GET', '/app/config', FakeReply(200, configJson()));
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('I am a freelancer'), findsOneWidget);
  });

  testWidgets('other failures keep their own messages', (tester) async {
    await pumpApp(
      tester,
      arrange: (adapter, store) => adapter.setReply(
        'GET',
        '/app/config',
        FakeReply(503, apiError('service_unavailable')),
      ),
    );
    expect(
      find.text(
        'The service is temporarily unavailable. Please try again soon.',
      ),
      findsOneWidget,
    );
  });

  testWidgets(
    'the message names both causes: an old server and a wrong address',
    (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.setReply(
          'GET',
          '/app/config',
          FakeReply(404, apiError('not_found')),
        ),
      );
      expect(find.textContaining('may need updating'), findsOneWidget);
      expect(
        find.textContaining('server address may be wrong'),
        findsOneWidget,
      );
    },
  );

  test('the texts shown before the config loads are kept in one place and hold no role word', () {
    for (final text in [
      BootstrapStrings.appName,
      BootstrapStrings.tryAgain,
      BootstrapStrings.serverMismatch,
    ]) {
      expect(
        text,
        isNot(
          matches(
            RegExp(
              r'freelancer|work ?host|organisation|church|provider|searcher',
              caseSensitive: false,
            ),
          ),
        ),
      );
    }
  });
}
