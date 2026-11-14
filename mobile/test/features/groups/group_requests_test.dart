import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _page(List<Object?> items, [int? total]) => {
  'items': items,
  'total': total ?? items.length,
};

Map<String, Object?> _request({
  String id = 'r1',
  String name = 'Harbour',
  String state = 'open',
  bool leads = false,
  Map<String, Object?>? group = const {'id': 'g1', 'name': 'Riverside'},
}) => {
  'id': id,
  'group_name': name,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'requester': {'id': 'p9', 'name': 'Pia Provider'},
  'state': state,
  'created_at': '2026-11-12T08:00:00Z',
  'requester_leads_a_group': leads,
  'requester_group': group,
};

Map<String, Object?> _member(
  String id,
  String name, [
  String status = 'provider',
]) => {
  'id': id,
  'full_name': name,
  'status': status,
  'home_group': {'id': 'g1', 'name': 'Riverside'},
  'status_set_by': null,
  'flagged_for_recheck': false,
};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

Future<TestApp> _open(
  WidgetTester tester,
  Map<String, Object?> me, {
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, me);
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply('GET', '/group-requests', FakeReply(200, _page([])));
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'group-requests');
  return app;
}

Map<String, Object?> _provider() =>
    personJson(status: 'provider', name: 'Pia Provider');
Map<String, Object?> _admin({bool leads = true}) => personJson(
  status: 'admin',
  name: 'Ada Admin',
  leader: leads ? 'Ada Admin' : 'Lena Leader',
);

Future<void> _choose(WidgetTester tester, String key, String label) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

void main() {
  group('a member asks for a group', () {
    testWidgets('sends the name, says it waits, and lists their request', (
      tester,
    ) async {
      final app = await _open(tester, _provider());
      await tester.enterText(find.byKey(const Key('group-name')), ' Harbour ');
      await tester.pumpAndSettle();
      app.adapter
        ..setReply(
          'POST',
          '/group-requests',
          FakeReply(201, {'request': _request(), 'group': null}),
        )
        ..setReply(
          'GET',
          '/group-requests',
          FakeReply(200, _page([_request()])),
        );
      await tapKey(tester, 'ask');
      expect(find.textContaining('Your request was sent'), findsOneWidget);
      final post = app.adapter.seen.firstWhere(
        (r) => r.method == 'POST' && r.path == '/group-requests',
      );
      expect(post.body, {'group_name': 'Harbour'});
      expect(find.text('Harbour'), findsOneWidget);
      expect(find.byKey(const Key('approve-r1')), findsNothing);
    });

    testWidgets('keeps the button off for a name that is too short', (
      tester,
    ) async {
      await _open(tester, _provider());
      await tester.enterText(find.byKey(const Key('group-name')), 'H');
      await tester.pumpAndSettle();
      expect(
        tester.widget<FilledButton>(find.byKey(const Key('ask'))).onPressed,
        isNull,
      );
    });

    for (final c in [
      ('group_name_taken', 409, 'with this name already exists'),
      ('request_open', 409, 'already have a request waiting'),
      ('not_admitted', 403, 'not available to you yet'),
    ]) {
      testWidgets('puts ${c.$1} in words', (tester) async {
        final app = await _open(tester, _provider());
        app.adapter.setReply(
          'POST',
          '/group-requests',
          FakeReply(c.$2, _refusal(c.$1)),
        );
        await tester.enterText(find.byKey(const Key('group-name')), 'Harbour');
        await tester.pumpAndSettle();
        await tapKey(tester, 'ask');
        expect(find.textContaining(c.$3), findsOneWidget);
      });
    }

    testWidgets('is linked from the home of an admitted member', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('group-requests')), findsOneWidget);
    });

    testWidgets('says when there are none, and offers a retry on failure', (
      tester,
    ) async {
      final app = await _open(
        tester,
        _provider(),
        arrange: (a) => a.setReply(
          'GET',
          '/group-requests',
          FakeReply(500, _refusal('server_error')),
        ),
      );
      expect(find.byKey(const Key('retry')), findsOneWidget);
      app.adapter.setReply('GET', '/group-requests', FakeReply(200, _page([])));
      await tapKey(tester, 'retry');
      expect(find.text('No requests.'), findsOneWidget);
    });
  });

  group('an ADMIN decides', () {
    testWidgets('approves a request and reloads the list', (tester) async {
      final app = await _open(
        tester,
        _admin(leads: false),
        arrange: (a) => a
          ..setReply(
            'GET',
            '/group-requests',
            FakeReply(200, _page([_request()])),
          )
          ..reply(
            'POST',
            '/group-requests/r1/approve',
            FakeReply(200, {
              'group': {'id': 'g2', 'name': 'Harbour'},
            }),
          ),
      );
      expect(
        find.textContaining('Pia Provider asks to start Harbour'),
        findsOneWidget,
      );
      expect(find.textContaining('Grace Church'), findsWidgets);
      app.adapter.setReply('GET', '/group-requests', FakeReply(200, _page([])));
      await tapKey(tester, 'approve-r1');
      expect(find.textContaining('Harbour was started'), findsOneWidget);
      final post = app.adapter.seen.firstWhere(
        (r) => r.path == '/group-requests/r1/approve',
      );
      expect(post.body, {});
      expect(find.byKey(const Key('approve-r1')), findsNothing);
    });

    testWidgets(
      'does not fail when the screen is left before the answer comes',
      (tester) async {
        final gate = Completer<void>();
        await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/group-requests',
              FakeReply(200, _page([_request()])),
            )
            ..reply(
              'POST',
              '/group-requests/r1/decline',
              FakeReply(204, null, const {}, gate.future),
            ),
        );
        final decline = find.byKey(const Key('decline-r1'));
        await tester.ensureVisible(decline);
        await tester.tap(decline);
        await tester.pump();
        await tester.pageBack();
        await tester.pumpAndSettle();
        gate.complete();
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('declines a request', (tester) async {
      final app = await _open(
        tester,
        _admin(leads: false),
        arrange: (a) => a
          ..setReply(
            'GET',
            '/group-requests',
            FakeReply(200, _page([_request()])),
          )
          ..reply('POST', '/group-requests/r1/decline', FakeReply(204)),
      );
      await tapKey(tester, 'decline-r1');
      expect(find.text('The request was declined.'), findsOneWidget);
      expect(app.adapter.count('POST', '/group-requests/r1/decline'), 1);
    });

    testWidgets(
      "asks who leads the requester's group from its members, and needs a choice",
      (tester) async {
        final app = await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/group-requests',
              FakeReply(200, _page([_request(leads: true)])),
            )
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(
                200,
                _page([
                  _member('p9', 'Pia Provider', 'verifier'),
                  _member('m7', 'Sam Searcher', 'searcher'),
                ]),
              ),
            )
            ..reply(
              'POST',
              '/group-requests/r1/approve',
              FakeReply(200, {
                'group': {'id': 'g2', 'name': 'Harbour'},
              }),
            ),
        );
        expect(find.textContaining('Pia Provider leads a'), findsOneWidget);
        final members = app.adapter.seen.firstWhere(
          (r) => r.path == '/verifier/members',
        );
        expect(members.query['home_group_id'], 'g1');
        final approve = find.byKey(const Key('approve-r1'));
        await tester.ensureVisible(approve);
        expect(tester.widget<FilledButton>(approve).onPressed, isNull);
        await _choose(tester, 'successor-r1', 'Sam Searcher · Work host');
        await tapKey(tester, 'approve-r1');
        final post = app.adapter.seen.firstWhere(
          (r) => r.path == '/group-requests/r1/approve',
        );
        expect(post.body, {'successor_id': 'm7'});
      },
    );

    testWidgets('lets the requester\'s group close when they are alone in it', (
      tester,
    ) async {
      final app = await _open(
        tester,
        _admin(leads: false),
        arrange: (a) => a
          ..setReply(
            'GET',
            '/group-requests',
            FakeReply(200, _page([_request(leads: true)])),
          )
          ..reply(
            'GET',
            '/verifier/members',
            FakeReply(200, _page([_member('p9', 'Pia Provider', 'verifier')])),
          )
          ..reply(
            'POST',
            '/group-requests/r1/approve',
            FakeReply(200, {
              'group': {'id': 'g2', 'name': 'Harbour'},
            }),
          ),
      );
      final approve = find.byKey(const Key('approve-r1'));
      await tester.ensureVisible(approve);
      expect(tester.widget<FilledButton>(approve).onPressed, isNotNull);
      await tapKey(tester, 'approve-r1');
      final post = app.adapter.seen.firstWhere(
        (r) => r.path == '/group-requests/r1/approve',
      );
      expect(post.body, {});
    });

    testWidgets(
      'keeps Approve off and offers a retry when the members cannot be loaded',
      (tester) async {
        final app = await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/group-requests',
              FakeReply(200, _page([_request(leads: true)])),
            )
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(500, _refusal('server_error')),
            ),
        );
        final approve = find.byKey(const Key('approve-r1'));
        await tester.ensureVisible(approve);
        expect(tester.widget<FilledButton>(approve).onPressed, isNull);
        app.adapter.setReply(
          'GET',
          '/verifier/members',
          FakeReply(200, _page([_member('m7', 'Sam Searcher', 'searcher')])),
        );
        await tapKey(tester, 'retry-members');
        expect(find.byKey(const Key('successor-r1')), findsOneWidget);
      },
    );

    for (final c in [
      ('not_open', 'decided already'),
      ('successor_required', 'Choose who leads the'),
      ('requester_unavailable', 'no longer in the'),
      ('successor_not_member', 'Choose a member of that'),
    ]) {
      testWidgets('puts ${c.$1} of an approval in words', (tester) async {
        final app = await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/group-requests',
              FakeReply(200, _page([_request()])),
            )
            ..reply(
              'POST',
              '/group-requests/r1/approve',
              FakeReply(409, _refusal(c.$1)),
            ),
        );
        await tapKey(tester, 'approve-r1');
        expect(find.textContaining(c.$2), findsOneWidget);
        expect(app.adapter.count('POST', '/group-requests/r1/approve'), 1);
      });
    }

    testWidgets(
      'retries a reload that failed as a reload, not as a next page',
      (tester) async {
        final app = await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/group-requests',
              FakeReply(200, _page([_request()])),
            )
            ..reply(
              'POST',
              '/group-requests/r1/approve',
              FakeReply(200, {
                'group': {'id': 'g2', 'name': 'Harbour'},
              }),
            ),
        );
        // The reload after the approval fails.
        app.adapter.setReply(
          'GET',
          '/group-requests',
          FakeReply(500, _refusal('server_error')),
        );
        await tapKey(tester, 'approve-r1');
        expect(find.byKey(const Key('retry')), findsOneWidget);
        app.adapter.setReply(
          'GET',
          '/group-requests',
          FakeReply(200, _page([])),
        );
        await tapKey(tester, 'retry');
        // A reload starts from the first page; the decided request is gone.
        final reloads = app.adapter.seen
            .where((r) => r.path == '/group-requests' && r.method == 'GET')
            .toList();
        expect(reloads.last.query['offset'], 0);
        expect(find.byKey(const Key('approve-r1')), findsNothing);
        expect(find.text('No requests.'), findsOneWidget);
      },
    );

    testWidgets(
      'starts a group at once, choosing who leads their own, and refreshes who they are',
      (tester) async {
        final app = await _open(
          tester,
          _admin(),
          arrange: (a) => a
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(
                200,
                _page([
                  {..._member('p1', 'Ada Admin', 'admin')},
                  _member('m7', 'Sam Searcher', 'searcher'),
                ]),
              ),
            )
            ..reply(
              'POST',
              '/group-requests',
              FakeReply(201, {
                'request': _request(state: 'approved'),
                'group': {'id': 'g2', 'name': 'Harbour'},
              }),
            ),
        );
        final members = app.adapter.seen.firstWhere(
          (r) => r.path == '/verifier/members',
        );
        expect(members.query['home_group_id'], 'group-1');
        await tester.enterText(find.byKey(const Key('group-name')), 'Harbour');
        await tester.pumpAndSettle();
        final ask = find.byKey(const Key('ask'));
        await tester.ensureVisible(ask);
        expect(tester.widget<FilledButton>(ask).onPressed, isNull);
        await _choose(tester, 'own-successor', 'Sam Searcher · Work host');
        await tapKey(tester, 'ask');
        expect(
          find.textContaining('was started and you lead it'),
          findsOneWidget,
        );
        final post = app.adapter.seen.firstWhere(
          (r) => r.path == '/group-requests' && r.method == 'POST',
        );
        expect(post.body, {'group_name': 'Harbour', 'successor_id': 'm7'});
        expect(app.adapter.count('GET', '/me'), greaterThan(1));
      },
    );

    testWidgets(
      'asks no successor of an ADMIN who does not lead the group they belong to',
      (tester) async {
        final app = await _open(
          tester,
          _admin(leads: false),
          arrange: (a) => a.reply(
            'POST',
            '/group-requests',
            FakeReply(201, {
              'request': _request(state: 'approved'),
              'group': {'id': 'g2', 'name': 'Harbour'},
            }),
          ),
        );
        expect(find.byKey(const Key('own-successor')), findsNothing);
        expect(app.adapter.count('GET', '/verifier/members'), 0);
        await tester.enterText(find.byKey(const Key('group-name')), 'Harbour');
        await tester.pumpAndSettle();
        await tapKey(tester, 'ask');
        final post = app.adapter.seen.firstWhere(
          (r) => r.path == '/group-requests' && r.method == 'POST',
        );
        expect(post.body, {'group_name': 'Harbour'});
      },
    );
  });

  group('notifications about group requests', () {
    testWidgets('reads each kind in words', (tester) async {
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
                  'group_request_new',
                  'group_request_approved',
                  'group_request_declined',
                  'reinstated',
                ].indexed)
                  {
                    'id': 'n$i',
                    'kind': kind,
                    'subject': {'name': 'Lena Leader'},
                    'created_at': '2026-11-12T08:00:00Z',
                    'read': false,
                  },
              ],
              'total': 4,
              'unread_count': 4,
            }),
          );
        },
      );
      await tapKey(tester, 'notifications');
      expect(find.textContaining('Lena Leader asks to start a'), findsWidgets);
      expect(
        find.textContaining('Lena Leader approved your request'),
        findsWidgets,
      );
      expect(
        find.textContaining('Lena Leader declined your request'),
        findsWidgets,
      );
      expect(find.textContaining('Lena Leader brought you back'), findsWidgets);
      expect(find.text('Something happened'), findsNothing);
    });
  });
}
