import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/person/person_providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _page(List<Object?> items, [int? total]) => {
  'items': items,
  'total': total ?? items.length,
};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

const _groups = {
  'items': [
    {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
    {'id': 'g2', 'name': 'Harbour', 'leader_name': 'Hal Harbour'},
  ],
};

Map<String, Object?> _member(String id, String name, String status) => {
  'id': id,
  'full_name': name,
  'status': status,
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'status_set_by': null,
  'flagged_for_recheck': false,
};

Map<String, Object?> _admin() => personJson(status: 'admin', name: 'Ada Admin');

Future<void> _choose(WidgetTester tester, String key, String label) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

Future<TestApp> _groupsScreen(
  WidgetTester tester, {
  Map<String, Object?>? me,
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, me ?? _admin());
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
  await tapKey(tester, 'admin-groups');
  return app;
}

Future<void> _openReplace(WidgetTester tester) async {
  await tapKey(tester, 'replace-group-1');
}

void main() {
  group('who sees the groups', () {
    for (final status in ['admin', 'owner']) {
      testWidgets('shows the tile and the page to an $status', (tester) async {
        await _groupsScreen(
          tester,
          me: personJson(status: status, name: 'Pat'),
        );
        expect(find.text('Leader: Lena Leader'), findsOneWidget);
        expect(find.text('Leader: Hal Harbour'), findsOneWidget);
      });
    }

    for (final status in ['verifier', 'provider']) {
      testWidgets('shows no tile to a $status', (tester) async {
        await pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, personJson(status: status));
            adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
          },
        );
        expect(find.byKey(const Key('admin-groups')), findsNothing);
      });
    }

    test('only an ADMIN or the OWNER may open the page', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final status in ['admin', 'owner']) {
        expect(personMayVisit(of(status), '/member/groups'), isTrue);
      }
      for (final status in [
        'pending',
        'revoked',
        'searcher',
        'provider',
        'verifier',
      ]) {
        expect(
          personMayVisit(of(status), '/member/groups'),
          isFalse,
          reason: status,
        );
      }
    });

    testWidgets('offers a retry when the groups cannot be loaded', (
      tester,
    ) async {
      final app = await _groupsScreen(
        tester,
        arrange: (a) => a.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(500, _refusal('server_error')),
        ),
      );
      expect(find.byKey(const Key('retry')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/churches/church-1/home-groups',
        FakeReply(200, _groups),
      );
      await tapKey(tester, 'retry');
      expect(find.text('Leader: Lena Leader'), findsOneWidget);
    });
  });

  group('change the leader of a group', () {
    List<Object?> members() => [
      _member('p1', 'Lena Leader', 'verifier'),
      _member('p2', 'Sam Searcher', 'searcher'),
      _member('p3', 'Pia Provider', 'provider'),
    ];

    testWidgets(
      'chooses a member (not the leader) and what the old leader becomes',
      (tester) async {
        final app = await _groupsScreen(
          tester,
          arrange: (a) => a
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(200, _page(members())),
            )
            ..reply(
              'PUT',
              '/home-groups/group-1/leader',
              FakeReply(200, {
                'group': {'id': 'group-1', 'name': 'Riverside'},
                'leader': {'id': 'p3', 'name': 'Pia Provider'},
              }),
            ),
        );
        await _openReplace(tester);
        final ask = app.adapter.seen.firstWhere(
          (r) => r.path == '/verifier/members',
        );
        expect(ask.query['home_group_id'], 'group-1');
        final change = find.byKey(const Key('change-group-1'));
        await tester.ensureVisible(change);
        expect(tester.widget<FilledButton>(change).onPressed, isNull);
        await tester.tap(find.byKey(const Key('successor-group-1')));
        await tester.pumpAndSettle();
        expect(find.text('Lena Leader · Verifier'), findsNothing);
        await tester.tap(find.text('Pia Provider · Freelancer').last);
        await tester.pumpAndSettle();
        await _choose(tester, 'former-group-1', 'A work host');
        await tapKey(tester, 'change-group-1');
        expect(
          find.text('Pia Provider leads Riverside from now on.'),
          findsOneWidget,
        );
        final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
        expect(put.body, {
          'successor_id': 'p3',
          'former_leader_status': 'searcher',
        });
      },
    );

    testWidgets('offers a VERIFIER leader only provider or searcher', (
      tester,
    ) async {
      await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(200, _page(members())),
        ),
      );
      await _openReplace(tester);
      await tester.ensureVisible(find.byKey(const Key('former-group-1')));
      await tester.tap(find.byKey(const Key('former-group-1')));
      await tester.pumpAndSettle();
      expect(find.text('No change: they keep their status'), findsNothing);
      expect(find.text('A freelancer'), findsWidgets);
      expect(find.text('A work host'), findsWidgets);
    });

    testWidgets('offers an ADMIN leader only to keep their status', (
      tester,
    ) async {
      await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(
            200,
            _page([
              _member('p1', 'Lena Leader', 'admin'),
              _member('p2', 'Sam Searcher', 'searcher'),
            ]),
          ),
        ),
      );
      await _openReplace(tester);
      expect(find.text('No change: they keep their status'), findsOneWidget);
    });

    testWidgets('offers a namesake who is not the leader', (tester) async {
      await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(
            200,
            _page([
              _member('p1', 'Lena Leader', 'verifier'),
              _member('p5', 'Lena Leader', 'searcher'),
            ]),
          ),
        ),
      );
      await _openReplace(tester);
      await tester.tap(find.byKey(const Key('successor-group-1')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Lena Leader · Work host'), findsWidgets);
      expect(find.text('Lena Leader · Verifier'), findsNothing);
    });

    testWidgets('says when nobody else is in the group', (tester) async {
      await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(200, _page([_member('p1', 'Lena Leader', 'verifier')])),
        ),
      );
      await _openReplace(tester);
      expect(find.textContaining('Nobody else is in this'), findsOneWidget);
      expect(find.byKey(const Key('change-group-1')), findsNothing);
    });

    testWidgets(
      'tells the ADMIN when only the first page of members is shown',
      (tester) async {
        await _groupsScreen(
          tester,
          arrange: (a) => a.reply(
            'GET',
            '/verifier/members',
            FakeReply(
              200,
              _page([_member('p2', 'Sam Searcher', 'searcher')], 90),
            ),
          ),
        );
        await _openReplace(tester);
        expect(
          find.text('Only the first 1 of 90 members are shown.'),
          findsOneWidget,
        );
      },
    );

    testWidgets('offers a retry when the members cannot be loaded', (
      tester,
    ) async {
      final app = await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(500, _refusal('server_error')),
        ),
      );
      await _openReplace(tester);
      expect(find.byKey(const Key('retry-members-group-1')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/verifier/members',
        FakeReply(200, _page([_member('p2', 'Sam Searcher', 'searcher')])),
      );
      await tapKey(tester, 'retry-members-group-1');
      expect(find.byKey(const Key('successor-group-1')), findsOneWidget);
    });

    for (final c in [
      ('successor_not_member', 409, 'Choose a member of this'),
      ('invalid_choice', 422, 'does not fit this leader'),
      ('status_not_allowed', 403, 'A leader above you decided this'),
      ('state_changed', 409, 'changed meanwhile'),
    ]) {
      testWidgets('puts ${c.$1} in words', (tester) async {
        await _groupsScreen(
          tester,
          arrange: (a) => a
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(
                200,
                _page([_member('p2', 'Sam Searcher', 'searcher')]),
              ),
            )
            ..reply(
              'PUT',
              '/home-groups/group-1/leader',
              FakeReply(c.$2, _refusal(c.$1)),
            ),
        );
        await _openReplace(tester);
        await _choose(tester, 'successor-group-1', 'Sam Searcher · Work host');
        await tapKey(tester, 'change-group-1');
        expect(find.textContaining(c.$3), findsOneWidget);
      });
    }

    testWidgets('can be dropped, and starts clean when opened again', (
      tester,
    ) async {
      await _groupsScreen(
        tester,
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(200, _page([_member('p2', 'Sam Searcher', 'searcher')])),
        ),
      );
      await _openReplace(tester);
      await _choose(tester, 'successor-group-1', 'Sam Searcher · Work host');
      await tapKey(tester, 'close-group-1');
      await _openReplace(tester);
      final change = find.byKey(const Key('change-group-1'));
      await tester.ensureVisible(change);
      expect(tester.widget<FilledButton>(change).onPressed, isNull);
    });
  });

  group('on the page of one person', () {
    Map<String, Object?> detail({String status = 'searcher'}) => {
      'id': 'p2',
      'full_name': 'Sam Searcher',
      'mobile_number': '+971 50 123 4567',
      'status': status,
      'requested_status': null,
      'church': {'id': 'church-1', 'name': 'Grace Church'},
      'home_group': {'id': 'group-1', 'name': 'Riverside'},
      'status_set_by': {'name': 'Vic Verifier'},
      'flagged_for_recheck': false,
      'applied_at': '2026-11-10T08:00:00Z',
      'history': [],
      'chain_of_trust': [],
      'vouches': [],
      'can_admit_as_provider': false,
    };

    Future<TestApp> person(
      WidgetTester tester, {
      Map<String, Object?>? me,
      String status = 'searcher',
      void Function(FakeAdapter adapter)? arrange,
    }) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, me ?? _admin());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
            ..reply(
              'GET',
              '/verifier/members',
              FakeReply(
                200,
                _page([
                  {
                    'id': 'p2',
                    'full_name': 'Sam Searcher',
                    'status': status,
                    'home_group': null,
                    'status_set_by': null,
                    'flagged_for_recheck': false,
                  },
                ]),
              ),
            )
            ..reply(
              'GET',
              '/verifier/people/p2',
              FakeReply(200, detail(status: status)),
            )
            ..reply(
              'GET',
              '/churches/church-1/home-groups',
              FakeReply(200, _groups),
            );
          arrange?.call(adapter);
        },
      );
      await tapKey(tester, 'leader-members');
      await tapKey(tester, 'member-p2');
      return app;
    }

    testWidgets('an ADMIN moves a member to another group of the church', (
      tester,
    ) async {
      final app = await person(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/verifier/people/p2/move',
          FakeReply(200, {
            'person': {'id': 'p2', 'name': 'Sam Searcher'},
            'home_group': {'id': 'g2', 'name': 'Harbour'},
          }),
        ),
      );
      final move = find.byKey(const Key('move-member'));
      await tester.ensureVisible(move);
      expect(tester.widget<FilledButton>(move).onPressed, isNull);
      await tester.tap(find.byKey(const Key('move-member-to')));
      await tester.pumpAndSettle();
      expect(
        find.text('Riverside'),
        findsWidgets,
      ); // the current group is the fact above, not a choice
      await tester.tap(find.text('Harbour').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'move-member');
      expect(find.text('Sam Searcher moved to Harbour.'), findsOneWidget);
      final post = app.adapter.seen.firstWhere(
        (r) => r.path == '/verifier/people/p2/move',
      );
      expect(post.body, {'home_group_id': 'g2'});
      expect(find.text('Harbour'), findsWidgets);
      expect(app.adapter.count('GET', '/verifier/people/p2'), 1);
    });

    testWidgets(
      'forgets a chosen group that is gone when the groups are loaded again',
      (tester) async {
        final app = await person(tester);
        await _choose(tester, 'move-member-to', 'Harbour');
        app.adapter.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(200, {
            'items': [
              {
                'id': 'group-1',
                'name': 'Riverside',
                'leader_name': 'Lena Leader',
              },
              {'id': 'g3', 'name': 'Lakeside', 'leader_name': 'Kim'},
            ],
          }),
        );
        ProviderScope.containerOf(
          tester.element(find.byKey(const Key('move-member-to'))),
        ).invalidate(homeGroupsProvider('church-1'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final move = find.byKey(const Key('move-member'));
        await tester.ensureVisible(move);
        expect(tester.widget<FilledButton>(move).onPressed, isNull);
      },
    );

    testWidgets(
      'is not offered to a VERIFIER, nor for a leader or an applicant',
      (tester) async {
        await person(
          tester,
          me: personJson(status: 'verifier', name: 'Lena Leader'),
        );
        expect(find.byKey(const Key('move-member')), findsNothing);
      },
    );

    testWidgets('says why a leader cannot be moved', (tester) async {
      await person(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/verifier/people/p2/move',
          FakeReply(409, _refusal('leads_a_group')),
        ),
      );
      await _choose(tester, 'move-member-to', 'Harbour');
      await tapKey(tester, 'move-member');
      expect(find.textContaining('Change the leader first'), findsOneWidget);
    });

    testWidgets('an ADMIN revokes a VERIFIER with the successor of the group', (
      tester,
    ) async {
      final app = await person(
        tester,
        status: 'verifier',
        arrange: (a) => a
          ..reply(
            'GET',
            '/verifier/members',
            FakeReply(
              200,
              _page([
                _member('p2', 'Sam Searcher', 'verifier'),
                _member('p3', 'Pia Provider', 'provider'),
              ]),
            ),
          )
          ..reply(
            'PUT',
            '/verifier/people/p2/status',
            FakeReply(200, {
              'id': 'p2',
              'status': 'revoked',
              'home_group_id': null,
              'flagged_for_recheck': false,
            }),
          ),
      );
      await tapKey(tester, 'revoke-open');
      expect(find.textContaining('leads a'), findsWidgets);
      final confirm = find.byKey(const Key('revoke-confirm'));
      await tester.ensureVisible(confirm);
      expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
      await _choose(tester, 'revoke-successor', 'Pia Provider · Freelancer');
      await tapKey(tester, 'revoke-confirm');
      expect(find.text('Sam Searcher was revoked.'), findsOneWidget);
      final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
      expect(put.body, {'to': 'revoked', 'successor_id': 'p3'});
      final ask = app.adapter.seen.lastWhere(
        (r) => r.path == '/verifier/members',
      );
      expect(ask.query['home_group_id'], 'group-1');
    });

    testWidgets('revokes without a choice when they are alone in the group', (
      tester,
    ) async {
      final app = await person(
        tester,
        status: 'verifier',
        arrange: (a) => a
          ..reply(
            'GET',
            '/verifier/members',
            FakeReply(200, _page([_member('p2', 'Sam Searcher', 'verifier')])),
          )
          ..reply(
            'PUT',
            '/verifier/people/p2/status',
            FakeReply(200, {
              'id': 'p2',
              'status': 'revoked',
              'home_group_id': null,
              'flagged_for_recheck': false,
            }),
          ),
      );
      await tapKey(tester, 'revoke-open');
      expect(find.textContaining('closes with the revocation'), findsOneWidget);
      await tapKey(tester, 'revoke-confirm');
      final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
      expect(put.body, {'to': 'revoked'});
    });

    testWidgets(
      'keeps the button off and offers a retry when the members cannot be loaded',
      (tester) async {
        final app = await person(
          tester,
          status: 'verifier',
          arrange: (a) => a.reply(
            'GET',
            '/verifier/members',
            FakeReply(500, _refusal('server_error')),
          ),
        );
        await tapKey(tester, 'revoke-open');
        final confirm = find.byKey(const Key('revoke-confirm'));
        await tester.ensureVisible(confirm);
        expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
        app.adapter.setReply(
          'GET',
          '/verifier/members',
          FakeReply(200, _page([_member('p3', 'Pia Provider', 'provider')])),
        );
        await tapKey(tester, 'retry-members');
        expect(find.byKey(const Key('revoke-successor')), findsOneWidget);
      },
    );

    testWidgets('a VERIFIER may not revoke a VERIFIER, and is told so', (
      tester,
    ) async {
      await person(
        tester,
        me: personJson(status: 'verifier', name: 'Lena Leader'),
        status: 'verifier',
      );
      expect(find.byKey(const Key('revoke-open')), findsNothing);
      expect(find.textContaining('Only an'), findsOneWidget);
    });
  });
}
