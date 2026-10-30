import 'package:flutter_test/flutter_test.dart';

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
}
