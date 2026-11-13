import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/leader/leader_providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _leader() =>
    personJson(status: 'verifier', name: 'Lena Leader');

Map<String, Object?> _applicant({
  String id = 'a1',
  String name = 'Nadia Applicant',
  String status = 'pending',
  String requested = 'provider',
  int vouches = 0,
  bool canProvider = false,
  List<Map<String, Object?>> vouchers = const [],
}) => {
  'id': id,
  'full_name': name,
  'status': status,
  'requested_status': requested,
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'applied_at': '2026-11-10T08:00:00Z',
  'vouch_count': vouches,
  'vouchers': vouchers,
  'can_admit_as_provider': canProvider,
};

Map<String, Object?> _page(List<Object?> items, [int? total]) => {
  'items': items,
  'total': total ?? items.length,
};

Map<String, Object?> _detail({
  String status = 'pending',
  String? requested = 'provider',
  List<Map<String, Object?>> vouches = const [],
}) => {
  'id': 'a1',
  'full_name': 'Nadia Applicant',
  'mobile_number': '+971 50 123 4567',
  'status': status,
  'requested_status': requested,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'status_set_by': null,
  'flagged_for_recheck': false,
  'applied_at': '2026-11-10T08:00:00Z',
  'history': [
    {
      'kind': 'signup',
      'from_status': null,
      'to_status': 'pending',
      'changed_by': null,
      'at': '2026-11-10T08:00:00Z',
    },
    {
      'kind': 'something_new',
      'from_status': 'pending',
      'to_status': 'searcher',
      'changed_by': {'name': 'Lena Leader'},
      'at': '2026-11-11T08:00:00Z',
    },
  ],
  'chain_of_trust': [
    {'id': 'p9', 'full_name': 'Lena Leader', 'status': 'verifier'},
    {'id': 'p8', 'full_name': '', 'status': 'owner'},
  ],
  'vouches': vouches,
};

const _live = {
  'name': 'Vera Voucher',
  'church_name': 'Hope Church',
  'live': true,
};
const _dead = {
  'name': 'Old Voucher',
  'church_name': 'Grace Church',
  'live': false,
};

Future<TestApp> _open(
  WidgetTester tester,
  String tile, {
  void Function(FakeAdapter adapter)? arrange,
  Map<String, Object?>? me,
  List<dynamic> overrides = const [],
}) async {
  final app = await pumpApp(
    tester,
    overrides: [...overrides],
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, me ?? _leader());
      adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, tile);
  return app;
}

void main() {
  group('the home of a leader', () {
    testWidgets('has the applicants and the members for a leader only', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _leader());
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('leader-applicants')), findsOneWidget);
      expect(find.byKey(const Key('leader-members')), findsOneWidget);
    });

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
      expect(find.byKey(const Key('leader-applicants')), findsNothing);
      expect(find.byKey(const Key('leader-members')), findsNothing);
    });

    test('only leaders may open the leader pages', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final path in [
        '/member/applicants',
        '/member/members',
        '/member/people/abc',
      ]) {
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

  group('the applicants', () {
    final list = _page([
      _applicant(vouches: 1, vouchers: [_live, _dead], canProvider: true),
      _applicant(id: 'a2', name: 'Sam Second', requested: 'searcher'),
    ]);

    testWidgets('shows who waits, with the vouches and no number', (
      tester,
    ) async {
      await _open(
        tester,
        'leader-applicants',
        arrange: (a) =>
            a.reply('GET', '/verifier/applicants', FakeReply(200, list)),
      );
      expect(find.text('Nadia Applicant'), findsOneWidget);
      expect(find.textContaining('In Riverside'), findsWidgets);
      expect(find.text('1 vouch · '.trim()), findsNothing);
      expect(find.textContaining('Vera Voucher, Hope Church'), findsOneWidget);
      expect(
        find.textContaining('Old Voucher, Grace Church · does not count'),
        findsOneWidget,
      );
      expect(find.textContaining('+971'), findsNothing);
    });

    testWidgets('admits as a searcher and takes the row off the list', (
      tester,
    ) async {
      final app = await _open(
        tester,
        'leader-applicants',
        arrange: (a) => a
          ..reply('GET', '/verifier/applicants', FakeReply(200, list))
          ..reply(
            'POST',
            '/verifier/people/a2/admit',
            FakeReply(200, {
              'id': 'a2',
              'status': 'searcher',
              'requested_status': null,
            }),
          ),
      );
      await tapKey(tester, 'admit-searcher-a2');
      expect(find.text('Sam Second was admitted.'), findsOneWidget);
      expect(find.text('Sam Second'), findsNothing);
      expect(
        app.adapter.seen
            .singleWhere((r) => r.path == '/verifier/people/a2/admit')
            .body,
        {'to': 'searcher'},
      );
    });

    testWidgets('the provider button works only when the server says it will', (
      tester,
    ) async {
      final app = await _open(
        tester,
        'leader-applicants',
        arrange: (a) => a
          ..reply('GET', '/verifier/applicants', FakeReply(200, list))
          ..reply(
            'POST',
            '/verifier/people/a1/admit',
            FakeReply(200, {
              'id': 'a1',
              'status': 'provider',
              'requested_status': null,
            }),
          ),
      );
      final off = tester.widget<FilledButton>(
        find.byKey(const Key('admit-provider-a2')),
      );
      expect(off.onPressed, isNull);
      expect(
        find.text('Offering skills needs a vouch from someone besides you.'),
        findsOneWidget,
      );
      await tapKey(tester, 'admit-provider-a1');
      expect(find.text('Nadia Applicant was admitted.'), findsOneWidget);
      expect(
        app.adapter.seen
            .singleWhere((r) => r.path == '/verifier/people/a1/admit')
            .body,
        {'to': 'provider'},
      );
    });

    for (final (status, code, expected) in [
      (409, 'not_enough_vouches', 'needs a vouch from someone besides you'),
      (409, 'not_pending', 'no longer waiting'),
      (409, 'state_changed', 'changed meanwhile'),
      (404, 'not_found', 'no longer exists'),
    ]) {
      testWidgets('explains a refused admission ($status $code)', (
        tester,
      ) async {
        await _open(
          tester,
          'leader-applicants',
          arrange: (a) => a
            ..reply('GET', '/verifier/applicants', FakeReply(200, list))
            ..reply(
              'POST',
              '/verifier/people/a2/admit',
              FakeReply(status, {
                'error': {'code': code, 'message': 'no'},
              }),
            ),
        );
        await tapKey(tester, 'admit-searcher-a2');
        expect(find.textContaining(expected), findsWidgets);
        expect(find.text('Sam Second'), findsOneWidget); // still listed
      });
    }

    testWidgets(
      'declining asks first, can be cancelled, and then closes the application',
      (tester) async {
        final app = await _open(
          tester,
          'leader-applicants',
          arrange: (a) => a
            ..reply('GET', '/verifier/applicants', FakeReply(200, list))
            ..reply('POST', '/verifier/people/a2/decline', FakeReply(204)),
        );
        await tapKey(tester, 'decline-open-a2');
        expect(app.adapter.count('POST', '/verifier/people/a2/decline'), 0);
        await tapKey(tester, 'decline-cancel-a2');
        expect(find.byKey(const Key('admit-searcher-a2')), findsOneWidget);
        await tapKey(tester, 'decline-open-a2');
        await tapKey(tester, 'decline-confirm-a2');
        expect(
          find.text('The application of Sam Second was declined.'),
          findsOneWidget,
        );
        expect(find.text('Sam Second'), findsNothing);
        expect(app.adapter.count('POST', '/verifier/people/a2/decline'), 1);
      },
    );

    testWidgets(
      'a searcher who asks to become a provider has only that to give',
      (tester) async {
        final app = await _open(
          tester,
          'leader-applicants',
          arrange: (a) => a
            ..reply(
              'GET',
              '/verifier/applicants',
              FakeReply(
                200,
                _page([
                  _applicant(
                    id: 'u1',
                    name: 'Una Upgrade',
                    status: 'searcher',
                    canProvider: true,
                  ),
                ]),
              ),
            )
            ..reply('POST', '/verifier/people/u1/decline', FakeReply(204)),
        );
        expect(find.byKey(const Key('admit-searcher-u1')), findsNothing);
        expect(find.byKey(const Key('admit-provider-u1')), findsOneWidget);
        await tapKey(tester, 'decline-open-u1');
        expect(find.textContaining('stays'), findsOneWidget);
        await tapKey(tester, 'decline-confirm-u1');
        expect(
          find.text('The request of Una Upgrade was declined.'),
          findsOneWidget,
        );
        expect(app.adapter.count('POST', '/verifier/people/u1/decline'), 1);
      },
    );

    testWidgets('says when nobody waits', (tester) async {
      await _open(
        tester,
        'leader-applicants',
        arrange: (a) =>
            a.reply('GET', '/verifier/applicants', FakeReply(200, _page([]))),
      );
      expect(find.text('Nobody is waiting to be admitted.'), findsOneWidget);
    });

    testWidgets('shows an error with a retry', (tester) async {
      final app = await _open(
        tester,
        'leader-applicants',
        arrange: (a) => a.reply(
          'GET',
          '/verifier/applicants',
          FakeReply(500, {
            'error': {'code': 'server_error', 'message': 'no'},
          }),
        ),
      );
      expect(find.byKey(const Key('retry')), findsOneWidget);
      app.adapter.setReply('GET', '/verifier/applicants', FakeReply(200, list));
      await tapKey(tester, 'retry');
      expect(find.text('Nadia Applicant'), findsOneWidget);
    });

    testWidgets('shows more when there are more than one page', (tester) async {
      final app = await _open(
        tester,
        'leader-applicants',
        arrange: (a) => a.reply(
          'GET',
          '/verifier/applicants',
          FakeReply(200, _page([_applicant()], 60)),
        ),
      );
      app.adapter.setReply(
        'GET',
        '/verifier/applicants',
        FakeReply(200, _page([_applicant(id: 'a9', name: 'Zed Later')], 60)),
      );
      await tapKey(tester, 'show-more');
      expect(find.text('Nadia Applicant'), findsOneWidget);
      expect(find.text('Zed Later'), findsOneWidget);
      expect(
        app.adapter.seen
            .where((r) => r.path == '/verifier/applicants')
            .last
            .query['offset'],
        1,
      );
    });
  });

  group('the members', () {
    final members = _page([
      {
        'id': 'm1',
        'full_name': 'Abe Member',
        'status': 'provider',
        'home_group': {'id': 'group-1', 'name': 'Riverside'},
        'status_set_by': {'name': 'Lena Leader'},
        'flagged_for_recheck': true,
      },
      {
        'id': 'm2',
        'full_name': 'Bea Member',
        'status': 'searcher',
        'home_group': null,
        'status_set_by': null,
        'flagged_for_recheck': false,
      },
    ]);

    testWidgets('lists the admitted with who admitted them and a flag', (
      tester,
    ) async {
      await _open(
        tester,
        'leader-members',
        arrange: (a) =>
            a.reply('GET', '/verifier/members', FakeReply(200, members)),
      );
      expect(
        find.textContaining(
          'Freelancer · Riverside · Admitted by Lena Leader · To be re-checked',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Bea Member'), findsOneWidget);
      expect(find.textContaining('+971'), findsNothing);
    });

    testWidgets('asks again with the status that is chosen', (tester) async {
      final app = await _open(
        tester,
        'leader-members',
        arrange: (a) =>
            a.reply('GET', '/verifier/members', FakeReply(200, members)),
      );
      expect(app.adapter.seen.last.query.containsKey('status'), isFalse);
      app.adapter.setReply(
        'GET',
        '/verifier/members',
        FakeReply(200, _page([(members['items']! as List).first])),
      );
      await tester.tap(find.byKey(const Key('members-filter')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Freelancer').last);
      await tester.pumpAndSettle();
      expect(app.adapter.seen.last.query['status'], 'provider');
      expect(find.text('Bea Member'), findsNothing);
    });

    testWidgets('says when nobody is admitted yet', (tester) async {
      await _open(
        tester,
        'leader-members',
        arrange: (a) =>
            a.reply('GET', '/verifier/members', FakeReply(200, _page([]))),
      );
      expect(find.text('Nobody has been admitted yet.'), findsOneWidget);
    });

    testWidgets('shows an error with a retry', (tester) async {
      await _open(
        tester,
        'leader-members',
        arrange: (a) => a.reply(
          'GET',
          '/verifier/members',
          FakeReply(500, {
            'error': {'code': 'server_error', 'message': 'no'},
          }),
        ),
      );
      expect(find.byKey(const Key('retry')), findsOneWidget);
    });
  });

  group('one person', () {
    Future<TestApp> person(
      WidgetTester tester, {
      Map<String, Object?>? detail,
      FakeReply? reply,
      List<String>? called,
    }) {
      return _open(
        tester,
        'leader-members',
        overrides: [
          if (called != null)
            dialerProvider.overrideWithValue((number) async {
              called.add(number);
              return true;
            }),
        ],
        arrange: (a) => a
          ..reply(
            'GET',
            '/verifier/members',
            FakeReply(
              200,
              _page([
                {
                  'id': 'a1',
                  'full_name': 'Nadia Applicant',
                  'status': 'pending',
                  'home_group': null,
                  'status_set_by': null,
                  'flagged_for_recheck': false,
                },
              ]),
            ),
          )
          ..reply(
            'GET',
            '/verifier/people/a1',
            reply ?? FakeReply(200, detail ?? _detail(vouches: [_live])),
          ),
      ).then((app) async {
        await tester.tap(find.byKey(const Key('member-a1')));
        await tester.pumpAndSettle();
        return app;
      });
    }

    testWidgets('shows the number, the history and the chain, and asks once', (
      tester,
    ) async {
      final called = <String>[];
      final app = await person(tester, called: called);
      expect(find.text('+971 50 123 4567'), findsOneWidget);
      expect(find.text('Grace Church'), findsOneWidget);
      expect(
        find.textContaining(
          'Signed up: — to Waiting to be admitted, by the system',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('something_new: Waiting to be admitted to'),
        findsOneWidget,
      );
      expect(find.textContaining('Lena Leader · '), findsWidgets);
      expect(
        find.textContaining('— · '),
        findsOneWidget,
      ); // the owner has no name left
      await tapKey(tester, 'call');
      expect(called, ['+971 50 123 4567']);
      expect(app.adapter.count('GET', '/verifier/people/a1'), 1);
    });

    testWidgets('admits from the page and updates it without asking again', (
      tester,
    ) async {
      final app = await person(tester);
      app.adapter.reply(
        'POST',
        '/verifier/people/a1/admit',
        FakeReply(200, {
          'id': 'a1',
          'status': 'provider',
          'requested_status': null,
        }),
      );
      await tapKey(tester, 'admit-provider-a1');
      expect(find.text('Nadia Applicant was admitted.'), findsOneWidget);
      expect(find.byKey(const Key('admit-searcher-a1')), findsNothing);
      expect(
        find.text('Freelancer'),
        findsOneWidget,
      ); // the new status, in the server's words
      expect(app.adapter.count('GET', '/verifier/people/a1'), 1);
    });

    testWidgets('a decline leaves a message and no details', (tester) async {
      final app = await person(tester);
      app.adapter.reply('POST', '/verifier/people/a1/decline', FakeReply(204));
      await tapKey(tester, 'decline-open-a1');
      await tapKey(tester, 'decline-confirm-a1');
      expect(
        find.text('The application of Nadia Applicant was declined.'),
        findsOneWidget,
      );
      expect(find.text('+971 50 123 4567'), findsNothing);
    });

    testWidgets('someone out of scope is not found, with no retry', (
      tester,
    ) async {
      await person(
        tester,
        reply: FakeReply(404, {
          'error': {'code': 'not_found', 'message': 'no'},
        }),
      );
      expect(find.byKey(const Key('retry')), findsNothing);
      expect(find.textContaining('no longer exists'), findsOneWidget);
    });

    testWidgets('a failure offers a retry that asks again', (tester) async {
      final app = await person(
        tester,
        reply: FakeReply(500, {
          'error': {'code': 'server_error', 'message': 'no'},
        }),
      );
      app.adapter.setReply(
        'GET',
        '/verifier/people/a1',
        FakeReply(200, _detail()),
      );
      await tapKey(tester, 'retry');
      expect(find.text('+971 50 123 4567'), findsOneWidget);
    });

    testWidgets('a searcher who asks to provide gets the upgrade controls', (
      tester,
    ) async {
      await person(
        tester,
        detail: _detail(
          status: 'searcher',
          requested: 'provider',
          vouches: [_live],
        ),
      );
      expect(find.byKey(const Key('admit-searcher-a1')), findsNothing);
      expect(find.byKey(const Key('admit-provider-a1')), findsOneWidget);
    });

    testWidgets('an admitted person has no admit controls', (tester) async {
      await person(
        tester,
        detail: _detail(status: 'provider', requested: null),
      );
      expect(find.byKey(const Key('admit-provider-a1')), findsNothing);
      expect(find.byKey(const Key('call')), findsOneWidget);
    });
  });
}
