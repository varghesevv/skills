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

Map<String, Object?> _leader() =>
    personJson(status: 'verifier', name: 'Lena Leader');

Map<String, Object?> _detail({
  String status = 'searcher',
  bool flagged = false,
  Map<String, Object?>? group = const {'id': 'group-1', 'name': 'Riverside'},
}) => {
  'id': 'p2',
  'full_name': 'Sam Searcher',
  'mobile_number': '+971 50 123 4567',
  'status': status,
  'requested_status': null,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': group,
  'status_set_by': {'name': 'Vic Verifier'},
  'flagged_for_recheck': flagged,
  'applied_at': '2026-11-10T08:00:00Z',
  'history': [],
  'chain_of_trust': [],
  'vouches': [],
  'can_admit_as_provider': false,
};

Map<String, Object?> _statusResult(
  String status, {
  String? group,
  bool flagged = false,
}) => {
  'id': 'p2',
  'status': status,
  'home_group_id': group,
  'flagged_for_recheck': flagged,
};

const _groups = {
  'items': [
    {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
    {'id': 'group-2', 'name': 'Harbour', 'leader_name': 'Hal Harbour'},
  ],
};

Map<String, Object?> _refusal(String code) => {
  'error': {'code': code, 'message': 'no', 'details': <String, Object?>{}},
};

/// Opens the person's page through the members list, as a leader does.
Future<TestApp> _person(
  WidgetTester tester, {
  Map<String, Object?>? detail,
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, _leader());
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
                'status': 'searcher',
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
          FakeReply(200, detail ?? _detail()),
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

Future<void> _choose(WidgetTester tester, String key, String label) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

void main() {
  group('the leader menu', () {
    testWidgets(
      'has the lists of the flagged and the revoked, for leaders only',
      (tester) async {
        await pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, _leader());
            adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
          },
        );
        expect(find.byKey(const Key('leader-flagged')), findsOneWidget);
        expect(find.byKey(const Key('leader-revoked')), findsOneWidget);
      },
    );

    testWidgets('a provider has neither', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(
            adapter,
            store,
            personJson(status: 'provider', name: 'Pia Provider'),
          );
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-flagged')), findsNothing);
      expect(find.byKey(const Key('leader-revoked')), findsNothing);
    });

    test('only leaders may open them', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final path in ['/member/revoked', '/member/flagged']) {
        for (final status in ['verifier', 'admin', 'owner']) {
          expect(
            personMayVisit(of(status), path),
            isTrue,
            reason: '$status $path',
          );
        }
        for (final status in ['pending', 'revoked', 'searcher', 'provider']) {
          expect(
            personMayVisit(of(status), path),
            isFalse,
            reason: '$status $path',
          );
        }
      }
    });
  });

  group('the revoked', () {
    Future<TestApp> open(WidgetTester tester, FakeReply reply) =>
        pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, _leader());
            adapter
              ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
              ..reply('GET', '/verifier/revoked', reply);
          },
        ).then((app) async {
          await tapKey(tester, 'leader-revoked');
          return app;
        });

    testWidgets('lists them with where they were removed from, and no number', (
      tester,
    ) async {
      await open(
        tester,
        FakeReply(
          200,
          _page([
            {
              'id': 'r1',
              'full_name': 'Rita Removed',
              'removed_from': {'id': 'group-1', 'name': 'Riverside'},
              'revoked_by': {'name': 'Lena Leader'},
              'revoked_at': '2026-11-12T08:00:00Z',
            },
          ]),
        ),
      );
      expect(find.text('Rita Removed'), findsOneWidget);
      expect(
        find.textContaining('Removed from Riverside, by Lena Leader'),
        findsOneWidget,
      );
      expect(find.textContaining('+971'), findsNothing);
    });

    testWidgets('says when nobody is revoked', (tester) async {
      await open(tester, FakeReply(200, _page([])));
      expect(find.text('Nobody is revoked.'), findsOneWidget);
    });

    testWidgets('offers a retry when the list cannot be loaded', (
      tester,
    ) async {
      final app = await open(tester, FakeReply(500, _refusal('server_error')));
      expect(find.byKey(const Key('retry')), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/verifier/revoked',
        FakeReply(200, _page([])),
      );
      await tapKey(tester, 'retry');
      expect(find.text('Nobody is revoked.'), findsOneWidget);
    });

    testWidgets('shows more when there are more than a page', (tester) async {
      final app = await open(
        tester,
        FakeReply(
          200,
          _page([
            {
              'id': 'r1',
              'full_name': 'First Removed',
              'removed_from': null,
              'revoked_by': null,
              'revoked_at': null,
            },
          ], 60),
        ),
      );
      app.adapter.setReply(
        'GET',
        '/verifier/revoked',
        FakeReply(
          200,
          _page([
            {
              'id': 'r2',
              'full_name': 'Second Removed',
              'removed_from': null,
              'revoked_by': null,
              'revoked_at': null,
            },
          ], 60),
        ),
      );
      await tapKey(tester, 'show-more');
      expect(find.text('First Removed'), findsOneWidget);
      expect(find.text('Second Removed'), findsOneWidget);
    });
  });

  group('the flagged', () {
    testWidgets('lists them with who set their status', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _leader());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
            ..reply(
              'GET',
              '/verifier/flagged',
              FakeReply(
                200,
                _page([
                  {
                    'id': 'f1',
                    'full_name': 'Fay Flagged',
                    'status': 'provider',
                    'home_group': {'id': 'group-1', 'name': 'Riverside'},
                    'status_set_by': {'name': 'Vic Verifier'},
                  },
                ]),
              ),
            );
        },
      );
      await tapKey(tester, 'leader-flagged');
      expect(find.text('Fay Flagged'), findsOneWidget);
      expect(find.textContaining('Set by Vic Verifier'), findsOneWidget);
      expect(find.textContaining('Riverside'), findsWidgets);
    });

    testWidgets(
      'the list asks again when a person page is left, so a confirmed person goes',
      (tester) async {
        final app = await pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, _leader());
            adapter
              ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
              ..reply(
                'GET',
                '/verifier/flagged',
                FakeReply(
                  200,
                  _page([
                    {
                      'id': 'p2',
                      'full_name': 'Sam Searcher',
                      'status': 'searcher',
                      'home_group': {'id': 'group-1', 'name': 'Riverside'},
                      'status_set_by': {'name': 'Vic Verifier'},
                    },
                  ]),
                ),
              )
              ..reply(
                'GET',
                '/verifier/people/p2',
                FakeReply(200, _detail(flagged: true)),
              )
              ..reply(
                'POST',
                '/verifier/people/p2/reconfirm',
                FakeReply(200, _statusResult('searcher', group: 'group-1')),
              );
          },
        );
        await tapKey(tester, 'leader-flagged');
        await tapKey(tester, 'flagged-p2');
        await tapKey(tester, 'reconfirm');
        // The server no longer lists the person once the flag is cleared.
        app.adapter.setReply(
          'GET',
          '/verifier/flagged',
          FakeReply(200, _page([])),
        );
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(app.adapter.count('GET', '/verifier/flagged'), 2);
        expect(find.text('Sam Searcher'), findsNothing);
        expect(find.text('Nobody needs a re-check.'), findsOneWidget);
      },
    );

    testWidgets(
      'a reload that failed is retried as a reload, from the first page',
      (tester) async {
        final app = await pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, _leader());
            adapter
              ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
              ..reply(
                'GET',
                '/verifier/flagged',
                FakeReply(
                  200,
                  _page([
                    {
                      'id': 'p2',
                      'full_name': 'Sam Searcher',
                      'status': 'searcher',
                      'home_group': null,
                      'status_set_by': null,
                    },
                  ]),
                ),
              )
              ..reply(
                'GET',
                '/verifier/people/p2',
                FakeReply(200, _detail(flagged: true)),
              )
              ..reply(
                'POST',
                '/verifier/people/p2/reconfirm',
                FakeReply(200, _statusResult('searcher')),
              );
          },
        );
        await tapKey(tester, 'leader-flagged');
        await tapKey(tester, 'flagged-p2');
        await tapKey(tester, 'reconfirm');
        // The reload on the way back fails; the stale row is still there.
        app.adapter.setReply(
          'GET',
          '/verifier/flagged',
          FakeReply(500, _refusal('server_error')),
        );
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('retry')), findsOneWidget);
        app.adapter.setReply(
          'GET',
          '/verifier/flagged',
          FakeReply(200, _page([])),
        );
        await tapKey(tester, 'retry');
        final asks = app.adapter.seen
            .where((r) => r.path == '/verifier/flagged')
            .toList();
        expect(asks.last.query['offset'], 0);
        expect(find.text('Nobody needs a re-check.'), findsOneWidget);
      },
    );

    testWidgets('says when nobody needs a re-check', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _leader());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
            ..reply('GET', '/verifier/flagged', FakeReply(200, _page([])));
        },
      );
      await tapKey(tester, 'leader-flagged');
      expect(find.text('Nobody needs a re-check.'), findsOneWidget);
    });
  });

  group('revoke', () {
    testWidgets('asks first, then revokes, and shows the person as revoked', (
      tester,
    ) async {
      final app = await _person(
        tester,
        arrange: (a) => a.reply(
          'PUT',
          '/verifier/people/p2/status',
          FakeReply(200, _statusResult('revoked')),
        ),
      );
      await tapKey(tester, 'revoke-open');
      expect(app.adapter.count('PUT', '/verifier/people/p2/status'), 0);
      expect(
        find.textContaining('Everyone whose status they set'),
        findsOneWidget,
      );
      await tapKey(tester, 'revoke-confirm');
      expect(find.text('Sam Searcher was revoked.'), findsOneWidget);
      expect(find.byKey(const Key('revoke-open')), findsNothing);
      final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
      expect(put.body, {'to': 'revoked'});
      expect(app.adapter.count('GET', '/verifier/people/p2'), 1);
      // The page shows who set the status now, and the change as the newest line of the history.
      expect(find.text('Vic Verifier'), findsNothing);
      expect(find.textContaining('Revoked: '), findsOneWidget);
      expect(find.textContaining('by Lena Leader'), findsOneWidget);
    });

    testWidgets('can be cancelled', (tester) async {
      final app = await _person(tester);
      await tapKey(tester, 'revoke-open');
      await tapKey(tester, 'revoke-cancel');
      expect(find.byKey(const Key('revoke-open')), findsOneWidget);
      expect(app.adapter.count('PUT', '/verifier/people/p2/status'), 0);
    });

    testWidgets('is not offered for a leader, who is told why', (tester) async {
      await _person(tester, detail: _detail(status: 'admin'));
      expect(find.byKey(const Key('revoke-open')), findsNothing);
      expect(find.textContaining('Hand that on first'), findsOneWidget);
    });

    testWidgets('is not offered for an applicant', (tester) async {
      await _person(tester, detail: _detail(status: 'pending'));
      expect(find.byKey(const Key('revoke-open')), findsNothing);
    });

    testWidgets("puts the server's refusal in words", (tester) async {
      await _person(
        tester,
        arrange: (a) => a.reply(
          'PUT',
          '/verifier/people/p2/status',
          FakeReply(403, _refusal('status_not_allowed')),
        ),
      );
      await tapKey(tester, 'revoke-open');
      await tapKey(tester, 'revoke-confirm');
      expect(
        find.textContaining('A leader above you decided this'),
        findsOneWidget,
      );
    });
  });

  group('reinstate', () {
    testWidgets('puts them in a chosen group with the chosen status', (
      tester,
    ) async {
      final app = await _person(
        tester,
        detail: _detail(status: 'revoked', group: null),
        arrange: (a) => a.reply(
          'PUT',
          '/verifier/people/p2/status',
          FakeReply(200, _statusResult('provider', group: 'group-2')),
        ),
      );
      expect(find.byKey(const Key('revoke-open')), findsNothing);
      final submit = find.byKey(const Key('reinstate-submit'));
      await tester.ensureVisible(submit);
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);
      await _choose(tester, 'reinstate-group', 'Harbour');
      await _choose(tester, 'reinstate-status', 'Freelancer');
      await tapKey(tester, 'reinstate-submit');
      expect(find.text('Sam Searcher is back.'), findsOneWidget);
      final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
      expect(put.body, {'to': 'provider', 'home_group_id': 'group-2'});
      expect(find.byKey(const Key('reinstate-submit')), findsNothing);
      expect(find.text('Harbour'), findsOneWidget);
      expect(find.text('Vic Verifier'), findsNothing);
      expect(find.textContaining('Reinstated: '), findsOneWidget);
    });

    testWidgets('says when the church has no open group', (tester) async {
      await _person(
        tester,
        detail: _detail(status: 'revoked', group: null),
        arrange: (a) => a.setReply(
          'GET',
          '/churches/church-1/home-groups',
          FakeReply(200, {'items': []}),
        ),
      );
      expect(find.textContaining('There is no open'), findsOneWidget);
      expect(find.byKey(const Key('reinstate-submit')), findsNothing);
    });

    testWidgets('shows the refusal when a higher leader revoked them', (
      tester,
    ) async {
      await _person(
        tester,
        detail: _detail(status: 'revoked', group: null),
        arrange: (a) => a.reply(
          'PUT',
          '/verifier/people/p2/status',
          FakeReply(403, _refusal('status_not_allowed')),
        ),
      );
      await _choose(tester, 'reinstate-group', 'Riverside');
      await tapKey(tester, 'reinstate-submit');
      expect(
        find.textContaining('A leader above you decided this'),
        findsOneWidget,
      );
    });

    testWidgets(
      'forgets a chosen group that is gone when the list is loaded again',
      (tester) async {
        final app = await _person(
          tester,
          detail: _detail(status: 'revoked', group: null),
        );
        await _choose(tester, 'reinstate-group', 'Harbour');
        // Harbour closes meanwhile; the next list no longer has it.
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
            ],
          }),
        );
        final container = ProviderScope.containerOf(
          tester.element(find.byKey(const Key('reinstate-group'))),
        );
        container.invalidate(homeGroupsProvider('church-1'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final submit = find.byKey(const Key('reinstate-submit'));
        await tester.ensureVisible(submit);
        expect(tester.widget<FilledButton>(submit).onPressed, isNull);
      },
    );

    testWidgets('offers a retry when the groups cannot be loaded', (
      tester,
    ) async {
      final app = await _person(
        tester,
        detail: _detail(status: 'revoked', group: null),
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
      expect(find.byKey(const Key('reinstate-group')), findsOneWidget);
    });
  });

  group('reconfirm', () {
    testWidgets('confirms a flagged status and clears the flag in place', (
      tester,
    ) async {
      final app = await _person(
        tester,
        detail: _detail(flagged: true),
        arrange: (a) => a.reply(
          'POST',
          '/verifier/people/p2/reconfirm',
          FakeReply(200, _statusResult('searcher', group: 'group-1')),
        ),
      );
      expect(
        find.textContaining('was set by someone who was revoked'),
        findsOneWidget,
      );
      await tapKey(tester, 'reconfirm');
      expect(
        find.text('The status of Sam Searcher is confirmed.'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('reconfirm')), findsNothing);
      expect(app.adapter.count('POST', '/verifier/people/p2/reconfirm'), 1);
      expect(app.adapter.count('GET', '/verifier/people/p2'), 1);
      // The caller is the new link, so the old one is no longer shown as having set it.
      expect(find.text('Vic Verifier'), findsNothing);
      expect(find.textContaining('Re-confirmed: '), findsOneWidget);
    });

    testWidgets('offers nothing when there is no flag', (tester) async {
      await _person(tester);
      expect(find.byKey(const Key('reconfirm')), findsNothing);
    });

    testWidgets('says so when the flag is already gone', (tester) async {
      await _person(
        tester,
        detail: _detail(flagged: true),
        arrange: (a) => a.reply(
          'POST',
          '/verifier/people/p2/reconfirm',
          FakeReply(409, _refusal('not_flagged')),
        ),
      );
      await tapKey(tester, 'reconfirm');
      expect(find.textContaining('no longer needs a re-check'), findsOneWidget);
    });
  });
}
