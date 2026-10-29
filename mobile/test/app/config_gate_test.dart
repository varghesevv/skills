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
}
