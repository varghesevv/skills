import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/person/person_providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

const _groups = {
  'items': [
    {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
    {'id': 'g2', 'name': 'Harbour', 'leader_name': 'Hal Harbour'},
  ],
};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

Map<String, Object?> _leader([String status = 'verifier']) =>
    personJson(status: status, name: 'Lena Leader', leader: 'Lena Leader');

const _closed = {
  'closed_group': {'id': 'group-1', 'name': 'Riverside'},
  'joined_group': {'id': 'g2', 'name': 'Harbour'},
  'status': 'searcher',
};

Future<TestApp> _open(
  WidgetTester tester, {
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
          '/churches/church-1/home-groups',
          FakeReply(200, _groups),
        );
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'leader-group');
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
  group('who sees it', () {
    testWidgets('a leader has the tile, a provider has not', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _leader());
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-group')), findsOneWidget);
    });

    testWidgets('a provider has no tile', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, personJson(status: 'provider'));
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-group')), findsNothing);
    });

    test('only leaders may open the page', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final status in ['verifier', 'admin', 'owner']) {
        expect(personMayVisit(of(status), '/member/group'), isTrue);
      }
      for (final status in ['pending', 'revoked', 'searcher', 'provider']) {
        expect(
          personMayVisit(of(status), '/member/group'),
          isFalse,
          reason: status,
        );
      }
    });
  });

  group('close my group', () {
    testWidgets(
      'asks first, then closes it, and the former leader lands on the home as a member',
      (tester) async {
        final app = await _open(
          tester,
          arrange: (a) => a
            ..reply(
              'POST',
              '/home-groups/group-1/close',
              FakeReply(200, _closed),
            )
            // After the closing the server says who they are now: a searcher in Harbour.
            ..reply(
              'GET',
              '/me',
              FakeReply(
                200,
                personJson(
                  status: 'searcher',
                  name: 'Lena Leader',
                  group: {'id': 'g2', 'name': 'Harbour'},
                  leader: 'Hal Harbour',
                ),
              ),
            ),
        );
        await _choose(tester, 'join', 'Harbour');
        await _choose(tester, 'former', 'A work host');
        await tapKey(tester, 'close-open');
        expect(app.adapter.count('POST', '/home-groups/group-1/close'), 0);
        expect(find.textContaining('It cannot be undone'), findsOneWidget);
        await tapKey(tester, 'close-confirm');
        await tester.pumpAndSettle();
        final post = app.adapter.seen.firstWhere(
          (r) => r.path == '/home-groups/group-1/close',
        );
        expect(post.body, {
          'move_to_group_id': 'g2',
          'former_leader_status': 'searcher',
        });
        // They are a member now: the home, with the outcome, and no leader pages.
        expect(
          find.text('Riverside is closed. You joined Harbour.'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('leader-group')), findsNothing);
        expect(find.byKey(const Key('leader-applicants')), findsNothing);
      },
    );

    testWidgets('can be backed out of at the question', (tester) async {
      final app = await _open(tester);
      await _choose(tester, 'join', 'Harbour');
      await tapKey(tester, 'close-open');
      await tapKey(tester, 'close-cancel');
      expect(find.byKey(const Key('close-open')), findsOneWidget);
      expect(app.adapter.count('POST', '/home-groups/group-1/close'), 0);
    });

    testWidgets(
      'keeps the status of an ADMIN, with no choice of what they become',
      (tester) async {
        final app = await _open(
          tester,
          me: _leader('admin'),
          arrange: (a) => a.reply(
            'POST',
            '/home-groups/group-1/close',
            FakeReply(200, {..._closed, 'status': 'admin'}),
          ),
        );
        expect(find.byKey(const Key('former')), findsNothing);
        await _choose(tester, 'join', 'Harbour');
        await tapKey(tester, 'close-open');
        await tapKey(tester, 'close-confirm');
        final post = app.adapter.seen.firstWhere(
          (r) => r.path == '/home-groups/group-1/close',
        );
        expect(post.body, {
          'move_to_group_id': 'g2',
          'former_leader_status': 'keep',
        });
      },
    );

    for (final c in [
      ('group_not_empty', 409, 'Others are still in this'),
      ('invalid_choice', 422, 'does not fit you'),
      ('state_changed', 409, 'changed meanwhile'),
    ]) {
      testWidgets('puts ${c.$1} in words', (tester) async {
        await _open(
          tester,
          arrange: (a) => a.reply(
            'POST',
            '/home-groups/group-1/close',
            FakeReply(c.$2, _refusal(c.$1)),
          ),
        );
        await _choose(tester, 'join', 'Harbour');
        await tapKey(tester, 'close-open');
        await tapKey(tester, 'close-confirm');
        expect(find.textContaining(c.$3), findsOneWidget);
        expect(find.byKey(const Key('close-open')), findsOneWidget);
      });
    }

    testWidgets('says when there is no other group to join', (tester) async {
      await _open(
        tester,
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
      expect(find.byKey(const Key('join')), findsOneWidget);
    });

    testWidgets(
      'forgets a chosen group that is gone when the groups are loaded again',
      (tester) async {
        final app = await _open(tester);
        await _choose(tester, 'join', 'Harbour');
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
        ProviderScope.containerOf(tester.element(find.byKey(const Key('join'))))
            .invalidate(homeGroupsProvider('church-1'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final open = find.byKey(const Key('close-open'));
        await tester.ensureVisible(open);
        expect(tester.widget<OutlinedButton>(open).onPressed, isNull);
      },
    );
  });
}
