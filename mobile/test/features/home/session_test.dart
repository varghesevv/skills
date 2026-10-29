import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

void main() {
  testWidgets('a saved session opens the dashboard without a login', (
    tester,
  ) async {
    final access = fresh('a');
    final refresh = fresh('r');
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) {
        // As after an app restart: only the refresh token survives in the keystore.
        store.save(accessToken: fresh('old'), refreshToken: refresh);
        store.clearAccessForRestart();
        adapter
          ..reply(
            'POST',
            '/auth/refresh',
            FakeReply(200, tokens(access, fresh('r2'))),
          )
          ..reply(
            'GET',
            '/me',
            FakeReply(200, meJson('organisation', name: 'Example Church')),
          );
      },
    );
    expect(find.text('Welcome, Example Church'), findsOneWidget);
    expect(app.adapter.count('POST', '/auth/refresh'), 1);
  });

  testWidgets('log out returns to the welcome screen and forgets the tokens', (
    tester,
  ) async {
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) {
        store.save(accessToken: fresh('a'), refreshToken: fresh('r'));
        store.clearAccessForRestart();
        adapter
          ..reply(
            'POST',
            '/auth/refresh',
            FakeReply(200, tokens(fresh('a'), fresh('r'))),
          )
          ..reply('GET', '/me', FakeReply(200, meJson('freelancer')))
          ..reply('POST', '/auth/logout', FakeReply(204));
      },
    );
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('log-out')));
    await tester.pumpAndSettle();
    expect(find.text('I am a freelancer'), findsOneWidget);
    expect(await app.store.readRefreshToken(), isNull);
    expect(app.adapter.count('POST', '/auth/logout'), 1);
  });

  testWidgets(
    'an expired session sends the person back to the welcome screen',
    (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          store.save(accessToken: fresh('a'), refreshToken: fresh('r'));
          store.clearAccessForRestart();
          adapter
            ..reply(
              'POST',
              '/auth/refresh',
              FakeReply(401, apiError('invalid_token')),
            )
            ..reply('GET', '/me', FakeReply(401, apiError('unauthorized')));
        },
      );
      expect(find.text('I am a freelancer'), findsOneWidget);
    },
  );
}
