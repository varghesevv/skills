import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Future<TestApp> _open(
  WidgetTester tester,
  Map<String, Object?> me, {
  void Function(FakeAdapter adapter)? arrange,
}) => pumpApp(
  tester,
  arrange: (adapter, store) {
    signedInAsPerson(adapter, store, me);
    adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
    arrange?.call(adapter);
  },
);

Future<void> _leave(WidgetTester tester, String password) async {
  await tapKey(tester, 'leave-open');
  await typeInto(tester, 'Your password, to confirm', password);
  await tapKey(tester, 'leave-submit');
}

void main() {
  group('an admitted member leaves', () {
    for (final status in ['searcher', 'provider']) {
      testWidgets(
        'a $status closes the account after the password, then is signed out',
        (tester) async {
          final password = fresh('pw');
          final app = await _open(
            tester,
            personJson(status: status, name: 'Pat Member'),
            arrange: (a) => a
              ..reply('DELETE', '/me', FakeReply(204))
              ..reply('POST', '/auth/logout', FakeReply(204)),
          );
          await _leave(tester, password);
          final delete = app.adapter.seen.firstWhere(
            (r) => r.method == 'DELETE',
          );
          expect(delete.path, '/me');
          expect(delete.body, {'password': password});
          expect(find.byKey(const Key('member-join')), findsOneWidget);
          expect(await app.store.readRefreshToken(), isNull);
        },
      );
    }

    testWidgets('a leader may ask, and is told to hand the group on first', (
      tester,
    ) async {
      final app = await _open(
        tester,
        personJson(
          status: 'verifier',
          name: 'Lena Leader',
          leader: 'Lena Leader',
        ),
        arrange: (a) =>
            a.reply('DELETE', '/me', FakeReply(409, apiError('leads_a_group'))),
      );
      await _leave(tester, fresh('pw'));
      expect(find.textContaining('You lead a'), findsOneWidget);
      expect(find.byKey(const Key('leave-submit')), findsOneWidget);
      expect(await app.store.readRefreshToken(), isNotNull);
    });

    for (final status in ['admin', 'owner']) {
      testWidgets('an $status is told to hand the role on first', (
        tester,
      ) async {
        await _open(
          tester,
          personJson(status: status, name: 'Pat Admin', leader: 'Lena Leader'),
          arrange: (a) => a.reply(
            'DELETE',
            '/me',
            FakeReply(409, apiError('leads_a_church')),
          ),
        );
        await _leave(tester, fresh('pw'));
        expect(find.textContaining('Hand that role on first'), findsOneWidget);
      });
    }

    testWidgets('a revoked person has no way to leave', (tester) async {
      await _open(
        tester,
        personJson(status: 'revoked', group: null, leader: null),
      );
      expect(find.byKey(const Key('leave-open')), findsNothing);
    });

    testWidgets('puts the other refusals in words and stays signed in', (
      tester,
    ) async {
      final app = await _open(
        tester,
        personJson(status: 'provider', name: 'Pia Provider'),
        arrange: (a) => a.reply(
          'DELETE',
          '/me',
          FakeReply(403, apiError('invalid_password')),
        ),
      );
      await _leave(tester, fresh('pw'));
      expect(find.text('The password is not correct.'), findsOneWidget);
      expect(await app.store.readRefreshToken(), isNotNull);
    });

    testWidgets('says an account that cannot be closed cannot be', (
      tester,
    ) async {
      await _open(
        tester,
        personJson(status: 'provider', name: 'Pia Provider'),
        arrange: (a) => a.reply(
          'DELETE',
          '/me',
          FakeReply(403, apiError('account_revoked')),
        ),
      );
      await _leave(tester, fresh('pw'));
      expect(find.text('This account cannot be closed.'), findsOneWidget);
    });

    testWidgets('can be cancelled before anything is sent', (tester) async {
      final app = await _open(tester, personJson(status: 'provider'));
      await tapKey(tester, 'leave-open');
      await tapKey(tester, 'leave-cancel');
      expect(find.byKey(const Key('leave-open')), findsOneWidget);
      expect(app.adapter.count('DELETE', '/me'), 0);
    });
  });
}
