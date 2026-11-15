import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

void main() {
  testWidgets('a saved session opens the member home without a login', (
    tester,
  ) async {
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) {
        // As after an app restart: only the refresh token survives in the keystore.
        signedInAsPerson(
          adapter,
          store,
          personJson(status: 'searcher', requested: null, name: 'Sam Searcher'),
        );
        adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
      },
    );
    expect(find.text('Welcome, Sam Searcher'), findsOneWidget);
    expect(app.adapter.count('POST', '/auth/refresh'), 1);
  });

  testWidgets('log out returns to the welcome screen and forgets the tokens', (
    tester,
  ) async {
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) {
        signedInAsProvider(adapter, store);
        adapter.reply('POST', '/auth/logout', FakeReply(204));
      },
    );
    await tester.tap(find.byKey(const Key('log-out')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('member-sign-in')), findsOneWidget);
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
      expect(find.byKey(const Key('member-sign-in')), findsOneWidget);
    },
  );

  testWidgets(
    'a session that expires while signed in returns to the welcome screen',
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
              FakeReply(200, tokens(fresh('a'), fresh('r'))),
            )
            ..reply(
              'GET',
              '/me',
              FakeReply(
                200,
                personJson(
                  status: 'provider',
                  requested: null,
                  name: 'Pat Example',
                ),
              ),
            )
            ..reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.text('Welcome, Pat Example'), findsOneWidget);
      // The API client signals this when the server rejects the refresh token.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(MaterialApp)),
      );
      container.read(sessionExpiredProvider.notifier).signal();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('member-sign-in')), findsOneWidget);
      expect(find.text('Welcome, Pat Example'), findsNothing);
    },
  );
}
