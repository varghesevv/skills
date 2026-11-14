import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

Map<String, Object?> _row(String id, String made, String until) => {
  'id': id,
  'created_at':
      '$made'
      'T08:00:00Z',
  'expires_at':
      '$until'
      'T08:00:00Z',
};

Map<String, Object?> _leader() =>
    personJson(status: 'verifier', name: 'Lena Leader');

Future<TestApp> _open(
  WidgetTester tester, {
  List<Object?> rows = const [],
  Map<String, Object?>? me,
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, me ?? _leader());
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply(
          'GET',
          '/verifier/group-invitations',
          FakeReply(200, {'items': rows}),
        );
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'leader-invitations');
  return app;
}

void main() {
  group('who sees it', () {
    testWidgets('a leader has the tile, a provider has not', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _leader());
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-invitations')), findsOneWidget);
    });

    testWidgets('a provider has no tile', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, personJson(status: 'provider'));
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-invitations')), findsNothing);
    });

    test('only leaders may open the page', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final status in ['verifier', 'admin', 'owner']) {
        expect(personMayVisit(of(status), '/member/invitations'), isTrue);
      }
      for (final status in ['pending', 'revoked', 'searcher', 'provider']) {
        expect(
          personMayVisit(of(status), '/member/invitations'),
          isFalse,
          reason: status,
        );
      }
    });
  });

  group('the links', () {
    testWidgets(
      'makes a link, shows it once with the token only in the link, and copies it',
      (tester) async {
        final token = fresh('tok');
        final copied = <String>[];
        tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          (call) async {
            if (call.method == 'Clipboard.setData') {
              copied.add((call.arguments as Map)['text'] as String);
            }
            return null;
          },
        );
        addTearDown(
          () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
            SystemChannels.platform,
            null,
          ),
        );
        final app = await _open(
          tester,
          arrange: (a) => a.reply(
            'POST',
            '/verifier/group-invitations',
            FakeReply(201, {
              'id': 'i1',
              'token': token,
              'expires_at': '2026-12-20T08:00:00Z',
            }),
          ),
        );
        expect(find.text('No link works now.'), findsOneWidget);
        app.adapter.setReply(
          'GET',
          '/verifier/group-invitations',
          FakeReply(200, {
            'items': [_row('i1', '2026-11-20', '2026-12-20')],
          }),
        );
        await tapKey(tester, 'make-join-link');
        expect(find.textContaining('/join/$token'), findsOneWidget);
        expect(find.textContaining('shown only now'), findsOneWidget);
        await tapKey(tester, 'copy-join-link');
        expect(copied.single, endsWith('/join/$token'));
        expect(find.text('Copied'), findsOneWidget);
        // The list shows the link that works, without its token, and no address holds the token.
        expect(find.byKey(const Key('invitation-i1')), findsOneWidget);
        expect(app.adapter.seen.any((r) => r.path.contains(token)), isFalse);
        expect(app.adapter.count('POST', '/verifier/group-invitations'), 1);
      },
    );

    testWidgets('lists the links that work and ends one', (tester) async {
      final app = await _open(
        tester,
        rows: [
          _row('i1', '2026-11-10', '2026-12-10'),
          _row('i2', '2026-11-12', '2026-12-12'),
        ],
        arrange: (a) =>
            a.reply('DELETE', '/verifier/group-invitations/i1', FakeReply(204)),
      );
      expect(find.byKey(const Key('invitation-i1')), findsOneWidget);
      expect(find.byKey(const Key('invitation-i2')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/verifier/group-invitations',
        FakeReply(200, {
          'items': [_row('i2', '2026-11-12', '2026-12-12')],
        }),
      );
      await tapKey(tester, 'revoke-invitation-i1');
      expect(find.text('The link no longer works.'), findsOneWidget);
      expect(find.byKey(const Key('invitation-i1')), findsNothing);
      expect(app.adapter.count('DELETE', '/verifier/group-invitations/i1'), 1);
    });

    testWidgets('ending the link that was just made takes it off the screen', (
      tester,
    ) async {
      final token = fresh('tok');
      final app = await _open(
        tester,
        arrange: (a) => a
          ..reply(
            'POST',
            '/verifier/group-invitations',
            FakeReply(201, {
              'id': 'i1',
              'token': token,
              'expires_at': '2026-12-20T08:00:00Z',
            }),
          )
          ..reply('DELETE', '/verifier/group-invitations/i1', FakeReply(204)),
      );
      app.adapter.setReply(
        'GET',
        '/verifier/group-invitations',
        FakeReply(200, {
          'items': [_row('i1', '2026-11-20', '2026-12-20')],
        }),
      );
      await tapKey(tester, 'make-join-link');
      expect(find.byKey(const Key('join-link')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/verifier/group-invitations',
        FakeReply(200, {'items': []}),
      );
      await tapKey(tester, 'revoke-invitation-i1');
      expect(find.byKey(const Key('join-link')), findsNothing);
      expect(find.byKey(const Key('copy-join-link')), findsNothing);
      expect(find.text('The link no longer works.'), findsOneWidget);
    });

    testWidgets('ending another link leaves the one just made on the screen', (
      tester,
    ) async {
      final token = fresh('tok');
      final app = await _open(
        tester,
        rows: [_row('i0', '2026-11-01', '2026-12-01')],
        arrange: (a) => a
          ..reply(
            'POST',
            '/verifier/group-invitations',
            FakeReply(201, {
              'id': 'i1',
              'token': token,
              'expires_at': '2026-12-20T08:00:00Z',
            }),
          )
          ..reply('DELETE', '/verifier/group-invitations/i0', FakeReply(204)),
      );
      await tapKey(tester, 'make-join-link');
      app.adapter.setReply(
        'GET',
        '/verifier/group-invitations',
        FakeReply(200, {
          'items': [_row('i1', '2026-11-20', '2026-12-20')],
        }),
      );
      await tapKey(tester, 'revoke-invitation-i0');
      expect(find.textContaining('/join/$token'), findsOneWidget);
    });

    testWidgets(
      'a failed ending does not stand next to the success of an earlier one',
      (tester) async {
        final app = await _open(
          tester,
          rows: [
            _row('i1', '2026-11-10', '2026-12-10'),
            _row('i2', '2026-11-12', '2026-12-12'),
          ],
          arrange: (a) => a
            ..reply('DELETE', '/verifier/group-invitations/i1', FakeReply(204))
            ..reply(
              'DELETE',
              '/verifier/group-invitations/i2',
              FakeReply(500, _refusal('server_error')),
            ),
        );
        app.adapter.setReply(
          'GET',
          '/verifier/group-invitations',
          FakeReply(200, {
            'items': [_row('i2', '2026-11-12', '2026-12-12')],
          }),
        );
        await tapKey(tester, 'revoke-invitation-i1');
        expect(find.text('The link no longer works.'), findsOneWidget);
        await tapKey(tester, 'revoke-invitation-i2');
        expect(find.text('The link no longer works.'), findsNothing);
        expect(find.textContaining('went wrong'), findsWidgets);
      },
    );

    testWidgets('says so for a leader who handed their group on', (
      tester,
    ) async {
      await _open(
        tester,
        arrange: (a) => a
          ..setReply(
            'GET',
            '/verifier/group-invitations',
            FakeReply(409, _refusal('no_home_group')),
          ),
      );
      expect(find.textContaining('do not lead a'), findsOneWidget);
    });

    testWidgets('puts a refused make in words', (tester) async {
      await _open(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/verifier/group-invitations',
          FakeReply(409, _refusal('no_home_group')),
        ),
      );
      await tapKey(tester, 'make-join-link');
      expect(find.textContaining('do not lead a'), findsOneWidget);
    });

    testWidgets('offers a retry when the links cannot be loaded', (
      tester,
    ) async {
      final app = await _open(
        tester,
        arrange: (a) => a.setReply(
          'GET',
          '/verifier/group-invitations',
          FakeReply(500, _refusal('server_error')),
        ),
      );
      expect(find.byKey(const Key('retry')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/verifier/group-invitations',
        FakeReply(200, {'items': []}),
      );
      await tapKey(tester, 'retry');
      expect(find.text('No link works now.'), findsOneWidget);
    });
  });
}
