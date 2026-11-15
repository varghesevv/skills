import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/features/person/person_providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _page(List<Object?> items, [int? total]) => {
  'items': items,
  'total': total ?? items.length,
};

const _groups = {
  'items': [
    {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
    {'id': 'g2', 'name': 'Harbour', 'leader_name': 'Hal Harbour'},
  ],
};

Map<String, Object?> _move({
  String id = 'm1',
  String state = 'open',
  bool fromLeader = false,
  bool toLeader = false,
  String personId = 'p7',
  String from = 'group-1',
  String to = 'g2',
}) => {
  'id': id,
  'person': {'id': personId, 'name': 'Sam Searcher'},
  'from_group': {'id': from, 'name': from == 'group-1' ? 'Riverside' : 'North'},
  'to_group': {'id': to, 'name': to == 'g2' ? 'Harbour' : 'South'},
  'agreed': {'person': true, 'from_leader': fromLeader, 'to_leader': toLeader},
  'state': state,
  'created_at': '2026-11-12T08:00:00Z',
};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

// The signed-in person belongs to group-1 (Riverside) and is p1; a leader there leads it.
Map<String, Object?> _provider() =>
    personJson(status: 'provider', name: 'Pia Provider');
Map<String, Object?> _leader() =>
    personJson(status: 'verifier', name: 'Lena Leader', leader: 'Lena Leader');

Future<TestApp> _open(
  WidgetTester tester,
  Map<String, Object?> me, {
  List<Object?> moves = const [],
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, me);
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply('GET', '/move-requests', FakeReply(200, _page(moves)))
        ..reply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(200, _groups),
        );
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'moves');
  return app;
}

Future<void> _choose(WidgetTester tester, String key, String label) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

void main() {
  group('asking to move', () {
    testWidgets('sends the chosen group and says the leaders were asked', (
      tester,
    ) async {
      final app = await _open(tester, _provider());
      expect(find.text('Riverside'), findsNothing);
      await _choose(tester, 'move-to', 'Harbour');
      app.adapter
        ..setReply(
          'POST',
          '/move-requests',
          FakeReply(201, _move(personId: 'p1')),
        )
        ..setReply(
          'GET',
          '/move-requests',
          FakeReply(200, _page([_move(personId: 'p1')])),
        );
      await tapKey(tester, 'move-ask');
      expect(
        find.textContaining('sent to the leaders of both'),
        findsOneWidget,
      );
      final post = app.adapter.seen.firstWhere(
        (r) => r.method == 'POST' && r.path == '/move-requests',
      );
      expect(post.body, {'home_group_id': 'g2'});
      expect(find.byKey(const Key('move-1')), findsNothing);
    });

    testWidgets('keeps the button off until a group is chosen', (tester) async {
      await _open(tester, _provider());
      final ask = find.byKey(const Key('move-ask'));
      await tester.ensureVisible(ask);
      expect(tester.widget<FilledButton>(ask).onPressed, isNull);
    });

    for (final c in [
      ('request_open', 409, 'already have a move waiting'),
      ('invalid_choice', 422, 'you belong to'),
      ('leads_a_group', 409, 'hands the'),
      ('not_admitted', 403, 'not available to you yet'),
    ]) {
      testWidgets('puts ${c.$1} in words', (tester) async {
        final app = await _open(tester, _provider());
        app.adapter.setReply(
          'POST',
          '/move-requests',
          FakeReply(c.$2, _refusal(c.$1)),
        );
        await _choose(tester, 'move-to', 'Harbour');
        await tapKey(tester, 'move-ask');
        expect(find.textContaining(c.$3), findsWidgets);
      });
    }

    testWidgets('offers no form to a leader, who is told to ask the ADMIN', (
      tester,
    ) async {
      await _open(tester, _leader());
      expect(find.byKey(const Key('move-to')), findsNothing);
      expect(find.textContaining('hands the'), findsOneWidget);
    });

    testWidgets('says when there is no other group', (tester) async {
      await _open(
        tester,
        _provider(),
        arrange: (a) => a.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(200, {
            'items': [
              {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'L'},
            ],
          }),
        ),
      );
      expect(find.textContaining('There is no other open'), findsOneWidget);
    });

    testWidgets('offers a retry when the groups cannot be loaded', (
      tester,
    ) async {
      final app = await _open(
        tester,
        _provider(),
        arrange: (a) => a.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(500, _refusal('server_error')),
        ),
      );
      expect(find.byKey(const Key('retry-groups')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/churches/church-1/home-groups',
        FakeReply(200, _groups),
      );
      await tapKey(tester, 'retry-groups');
      expect(find.byKey(const Key('move-to')), findsOneWidget);
    });

    testWidgets(
      'forgets a chosen group that is gone when the list is loaded again',
      (tester) async {
        final app = await _open(tester, _provider());
        await _choose(tester, 'move-to', 'Harbour');
        app.adapter.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(200, {
            'items': [
              {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'L'},
              {'id': 'g3', 'name': 'Lakeside', 'leader_name': 'K'},
            ],
          }),
        );
        ProviderScope.containerOf(
          tester.element(find.byKey(const Key('move-to'))),
        ).invalidate(homeGroupsProvider('church-1'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final ask = find.byKey(const Key('move-ask'));
        await tester.ensureVisible(ask);
        expect(tester.widget<FilledButton>(ask).onPressed, isNull);
      },
    );
  });

  group('the moves that concern me', () {
    testWidgets('shows who agreed, and gives the member only a cancel', (
      tester,
    ) async {
      await _open(
        tester,
        personJson(status: 'provider', name: 'Sam Searcher'),
        moves: [_move(personId: 'p1')],
      );
      expect(find.text('Sam Searcher: Riverside to Harbour'), findsOneWidget);
      expect(find.text('The member agreed'), findsOneWidget);
      expect(find.text('Waiting for the leader they leave'), findsOneWidget);
      expect(find.text('Waiting for the leader they join'), findsOneWidget);
      expect(find.byKey(const Key('agree-m1')), findsNothing);
      expect(find.byKey(const Key('cancel-m1')), findsOneWidget);
    });

    testWidgets(
      'lets the leader of the group they leave agree, and says they moved on the last one',
      (tester) async {
        final app = await _open(
          tester,
          _leader(),
          moves: [_move(toLeader: true)],
          arrange: (a) => a.reply(
            'POST',
            '/move-requests/m1/agree',
            FakeReply(
              200,
              _move(state: 'completed', fromLeader: true, toLeader: true),
            ),
          ),
        );
        await tapKey(tester, 'agree-m1');
        expect(find.text('Sam Searcher moved.'), findsOneWidget);
        expect(app.adapter.count('POST', '/move-requests/m1/agree'), 1);
      },
    );

    testWidgets(
      'says the member moves when both leaders have, after the first agreement',
      (tester) async {
        await _open(
          tester,
          _leader(),
          moves: [_move()],
          arrange: (a) => a.reply(
            'POST',
            '/move-requests/m1/agree',
            FakeReply(200, _move(fromLeader: true)),
          ),
        );
        await tapKey(tester, 'agree-m1');
        expect(
          find.textContaining('moves when both leaders have'),
          findsOneWidget,
        );
      },
    );

    testWidgets('offers no agree to a leader who agreed already', (
      tester,
    ) async {
      await _open(tester, _leader(), moves: [_move(fromLeader: true)]);
      expect(find.byKey(const Key('agree-m1')), findsNothing);
      expect(find.byKey(const Key('cancel-m1')), findsOneWidget);
    });

    testWidgets('offers nothing to a leader of neither group', (tester) async {
      await _open(
        tester,
        _leader(),
        moves: [_move(from: 'g8', to: 'g9')],
      );
      expect(find.text('Sam Searcher: North to South'), findsOneWidget);
      expect(find.byKey(const Key('agree-m1')), findsNothing);
      expect(find.byKey(const Key('cancel-m1')), findsNothing);
    });

    testWidgets('cancels a move', (tester) async {
      final app = await _open(
        tester,
        personJson(status: 'provider', name: 'Sam Searcher'),
        moves: [_move(personId: 'p1')],
        arrange: (a) => a.reply(
          'POST',
          '/move-requests/m1/cancel',
          FakeReply(200, _move(state: 'cancelled', personId: 'p1')),
        ),
      );
      await tapKey(tester, 'cancel-m1');
      expect(find.text('The move was cancelled.'), findsOneWidget);
      expect(app.adapter.count('POST', '/move-requests/m1/cancel'), 1);
    });

    testWidgets('shows decided moves without buttons', (tester) async {
      await _open(
        tester,
        _leader(),
        moves: [_move(state: 'completed', fromLeader: true, toLeader: true)],
      );
      expect(find.text('Done · Nov 12, 2026'), findsOneWidget);
      expect(find.byKey(const Key('agree-m1')), findsNothing);
      expect(find.byKey(const Key('cancel-m1')), findsNothing);
    });

    for (final c in [
      ('not_open', 'decided already'),
      ('already_agreed', 'You agreed already'),
      ('request_stale', 'no longer in that'),
    ]) {
      testWidgets('puts ${c.$1} of an agreement in words', (tester) async {
        await _open(
          tester,
          _leader(),
          moves: [_move()],
          arrange: (a) => a.reply(
            'POST',
            '/move-requests/m1/agree',
            FakeReply(409, _refusal(c.$1)),
          ),
        );
        await tapKey(tester, 'agree-m1');
        expect(find.textContaining(c.$2), findsOneWidget);
      });
    }

    testWidgets(
      'retries a reload that failed as a reload, from the first page',
      (tester) async {
        final app = await _open(
          tester,
          personJson(status: 'provider', name: 'Sam Searcher'),
          moves: [_move(personId: 'p1')],
          arrange: (a) => a.reply(
            'POST',
            '/move-requests/m1/cancel',
            FakeReply(200, _move(state: 'cancelled', personId: 'p1')),
          ),
        );
        app.adapter.setReply(
          'GET',
          '/move-requests',
          FakeReply(500, _refusal('server_error')),
        );
        await tapKey(tester, 'cancel-m1');
        expect(find.byKey(const Key('retry')), findsOneWidget);
        app.adapter.setReply(
          'GET',
          '/move-requests',
          FakeReply(200, _page([])),
        );
        await tapKey(tester, 'retry');
        final asks = app.adapter.seen
            .where((r) => r.path == '/move-requests' && r.method == 'GET')
            .toList();
        expect(asks.last.query['offset'], 0);
        expect(find.text('No moves.'), findsOneWidget);
      },
    );

    testWidgets('says when there are none', (tester) async {
      await _open(tester, _provider());
      expect(find.text('No moves.'), findsOneWidget);
    });

    testWidgets(
      'does not fail when the screen is left before the answer comes',
      (tester) async {
        final gate = Completer<void>();
        await _open(
          tester,
          personJson(status: 'provider', name: 'Sam Searcher'),
          moves: [_move(personId: 'p1')],
          arrange: (a) => a.reply(
            'POST',
            '/move-requests/m1/cancel',
            FakeReply(
              200,
              _move(state: 'cancelled', personId: 'p1'),
              const {},
              gate.future,
            ),
          ),
        );
        final cancel = find.byKey(const Key('cancel-m1'));
        await tester.ensureVisible(cancel);
        await tester.tap(cancel);
        await tester.pump();
        await tester.pageBack();
        await tester.pumpAndSettle();
        gate.complete();
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('says the member has not agreed when the server says so', (
      tester,
    ) async {
      final unagreed = _move();
      (unagreed['agreed'] as Map<String, Object?>)['person'] = false;
      await _open(tester, _leader(), moves: [unagreed]);
      expect(find.text('Waiting for the member'), findsOneWidget);
      expect(find.text('The member agreed'), findsNothing);
    });
  });

  group('the home and the notifications', () {
    testWidgets('the link is on the home of an admitted member', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('moves')), findsOneWidget);
    });

    testWidgets('each kind of notification about a move reads in words', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply(
            'GET',
            '/me/notifications',
            FakeReply(200, {
              'items': [
                for (final (i, kind) in [
                  'move_requested',
                  'move_completed',
                  'move_cancelled',
                  'member_moved_in',
                  'member_moved_out',
                ].indexed)
                  {
                    'id': 'n$i',
                    'kind': kind,
                    'subject': {'name': 'Lena Leader'},
                    'created_at': '2026-11-12T08:00:00Z',
                    'read': false,
                  },
              ],
              'total': 5,
              'unread_count': 5,
            }),
          );
        },
      );
      await tapKey(tester, 'notifications');
      expect(find.textContaining('Lena Leader asks to move'), findsWidgets);
      expect(find.textContaining('Lena Leader moved you'), findsWidgets);
      expect(
        find.textContaining('A move was cancelled by Lena Leader'),
        findsWidgets,
      );
      expect(find.textContaining('Lena Leader joined your'), findsWidgets);
      expect(find.textContaining('Lena Leader left your'), findsWidgets);
      expect(find.text('Something happened'), findsNothing);
    });
  });
}
