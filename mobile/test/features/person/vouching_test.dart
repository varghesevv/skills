import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/person/data/vouching_models.dart';
import 'package:skills_app/features/person/vouch_paste_dialog.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _emptyNotes = {'items': [], 'total': 0, 'unread_count': 0};
const _noVouches = {'items': []};

void _applicantLists(FakeAdapter adapter) => adapter
  ..reply(
    'GET',
    '/churches',
    FakeReply(200, {
      'items': [
        {'id': 'church-1', 'name': 'Grace Church'},
      ],
    }),
  )
  ..reply(
    'GET',
    '/churches/church-1/home-groups',
    FakeReply(200, {
      'items': [
        {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
      ],
    }),
  )
  ..reply('GET', '/me/vouches', FakeReply(200, _noVouches))
  ..reply('GET', '/me/notifications', FakeReply(200, _emptyNotes));

Map<String, Object?> _provider() =>
    personJson(status: 'provider', name: 'Pia Provider');

Map<String, Object?> _info({bool already = false}) => {
  'applicant_name': 'Nadia Applicant',
  'church_name': 'Grace Church',
  'home_group_name': 'Riverside',
  'requested_status': 'provider',
  'already_vouched': already,
};

/// A member opens the page for a pasted link.
Future<TestApp> _openLink(
  WidgetTester tester,
  String token, {
  FakeReply? lookup,
  FakeReply? vouch,
}) async {
  final app = await pumpApp(
    tester,
    arrange: (adapter, store) {
      signedInAsPerson(adapter, store, _provider());
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _emptyNotes))
        ..reply(
          'POST',
          '/vouch-links/lookup',
          lookup ?? FakeReply(200, _info()),
        )
        ..reply(
          'POST',
          '/vouch-links/vouch',
          vouch ?? FakeReply(201, {'id': 'v1'}),
        );
    },
  );
  await tapKey(tester, 'vouch-for-someone');
  await tester.enterText(
    find.byKey(const Key('vouch-link-field')),
    'https://demo.example.org/vouch/$token?utm=1',
  );
  await tapKey(tester, 'vouch-link-open');
  return app;
}

void main() {
  group('sharing my vouch link', () {
    testWidgets('shows the link once when it is made and copies it', (
      tester,
    ) async {
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
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _applicantLists(adapter);
          signedInAsPerson(adapter, store);
          adapter
            ..reply(
              'GET',
              '/me/vouch-link',
              FakeReply(200, {'active': false, 'expires_at': null}),
            )
            ..reply(
              'POST',
              '/me/vouch-link',
              FakeReply(201, {
                'token': token,
                'expires_at': '2026-12-20T10:00:00Z',
              }),
            );
        },
      );
      expect(find.text('You have no link that works yet.'), findsOneWidget);
      await tapKey(tester, 'make-vouch-link');
      expect(find.textContaining('/vouch/$token'), findsOneWidget);
      expect(
        find.text('Copy this link now. It is not shown again.'),
        findsOneWidget,
      );
      await tapKey(tester, 'copy-vouch-link');
      expect(copied.single, endsWith('/vouch/$token'));
      expect(find.text('Copied'), findsOneWidget);
      expect(app.adapter.count('POST', '/me/vouch-link'), 1);
    });

    testWidgets('after a reload says only that a link works', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _applicantLists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply(
            'GET',
            '/me/vouch-link',
            FakeReply(200, {
              'active': true,
              'expires_at': '2026-12-20T10:00:00Z',
            }),
          );
        },
      );
      expect(find.textContaining('You have a link that works until'), findsOne);
      expect(find.byKey(const Key('vouch-link')), findsNothing);
      expect(find.text('Make a new link'), findsOneWidget);
    });

    testWidgets('says why making a link failed', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _applicantLists(adapter);
          signedInAsPerson(adapter, store);
          adapter
            ..reply(
              'GET',
              '/me/vouch-link',
              FakeReply(200, {'active': false, 'expires_at': null}),
            )
            ..reply(
              'POST',
              '/me/vouch-link',
              FakeReply(
                429,
                {
                  'error': {'code': 'rate_limited', 'message': 'slow down'},
                },
                {
                  'retry-after': ['120'],
                },
              ),
            );
        },
      );
      await tapKey(tester, 'make-vouch-link');
      expect(find.textContaining('Too many requests'), findsOneWidget);
    });

    testWidgets('keeps the rest of the page when the vouching sections fail', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _applicantLists(adapter);
          signedInAsPerson(adapter, store);
          final broken = FakeReply(500, {
            'error': {'code': 'server_error', 'message': 'no'},
          });
          adapter
            ..setReply('GET', '/me/vouches', broken)
            ..reply('GET', '/me/vouch-link', broken);
        },
      );
      // Each failed section offers its own retry, and the form below still works.
      expect(find.text('Try again'), findsNWidgets(2));
      expect(
        find.text('Change your choice', skipOffstage: false),
        findsOneWidget,
      );
      app.adapter
        ..setReply(
          'GET',
          '/me/vouch-link',
          FakeReply(200, {'active': false, 'expires_at': null}),
        )
        ..setReply('GET', '/me/vouches', FakeReply(200, _noVouches));
      await tester.tap(find.text('Try again').first);
      await tester.pumpAndSettle();
      expect(find.text('You have no link that works yet.'), findsOneWidget);
    });

    testWidgets('lists the vouches received, marking those that do not count', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _applicantLists(adapter);
          signedInAsPerson(adapter, store, personJson(vouches: 1));
          adapter
            ..setReply(
              'GET',
              '/me/vouches',
              FakeReply(200, {
                'items': [
                  {
                    'id': 'v1',
                    'voucher_name': 'Vera Voucher',
                    'church_name': 'Hope Church',
                    'live': true,
                    'created_at': '2026-11-13T08:00:00Z',
                  },
                  {
                    'id': 'v2',
                    'voucher_name': 'Old Voucher',
                    'church_name': 'Grace Church',
                    'live': false,
                    'created_at': '2026-11-12T08:00:00Z',
                  },
                ],
              }),
            )
            ..reply(
              'GET',
              '/me/vouch-link',
              FakeReply(200, {'active': false, 'expires_at': null}),
            );
        },
      );
      expect(find.textContaining('Vera Voucher, Hope Church'), findsOneWidget);
      expect(find.textContaining('Old Voucher, Grace Church'), findsOneWidget);
      expect(find.textContaining('does not count now'), findsOneWidget);
    });
  });

  group('the page for a pasted vouch link', () {
    testWidgets('shows who asks and vouches, with the token in the body', (
      tester,
    ) async {
      final token = fresh('tok');
      final app = await _openLink(tester, token);
      expect(
        find.textContaining('Nadia Applicant from Grace Church, Riverside'),
        findsOneWidget,
      );
      final lookup = app.adapter.seen.singleWhere(
        (r) => r.path == '/vouch-links/lookup',
      );
      expect(lookup.body, {'token': token});
      await tapKey(tester, 'vouch-submit');
      expect(
        find.text('Thank you. You vouched for Nadia Applicant.'),
        findsOneWidget,
      );
      expect(
        app.adapter.seen
            .singleWhere((r) => r.path == '/vouch-links/vouch')
            .body,
        {'token': token},
      );
      expect(
        app.adapter.seen.every((r) => !r.path.contains(token)),
        isTrue,
        reason: 'the token never travels in an address',
      );
    });

    testWidgets('says so when the person has already vouched', (tester) async {
      await _openLink(
        tester,
        fresh('tok'),
        lookup: FakeReply(200, _info(already: true)),
      );
      expect(
        find.text('You have already vouched for Nadia Applicant.'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('vouch-submit')), findsNothing);
    });

    for (final (status, code, expected) in [
      (404, 'not_found', 'not valid any more'),
      (403, 'cannot_vouch_self', 'your own link'),
      (429, 'rate_limited', 'vouched many times today'),
    ]) {
      testWidgets('explains a refused lookup ($status $code)', (tester) async {
        await _openLink(
          tester,
          fresh('tok'),
          lookup: FakeReply(status, {
            'error': {'code': code, 'message': 'no'},
          }),
        );
        expect(find.textContaining(expected), findsOneWidget);
      });
    }

    for (final (status, code, expected) in [
      (409, 'already_vouched', 'already vouched for Nadia Applicant'),
      (429, 'rate_limited', 'vouched many times today'),
      (404, 'not_found', 'not valid any more'),
    ]) {
      testWidgets('explains a refused vouch ($status $code)', (tester) async {
        await _openLink(
          tester,
          fresh('tok'),
          vouch: FakeReply(status, {
            'error': {'code': code, 'message': 'no'},
          }),
        );
        await tapKey(tester, 'vouch-submit');
        expect(find.textContaining(expected), findsOneWidget);
        expect(find.byKey(const Key('vouch-submit')), findsOneWidget);
      });
    }

    testWidgets('a text with no token opens nothing', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply(
            'GET',
            '/me/notifications',
            FakeReply(200, _emptyNotes),
          );
        },
      );
      await tapKey(tester, 'vouch-for-someone');
      await tester.enterText(find.byKey(const Key('vouch-link-field')), 'hi');
      await tapKey(tester, 'vouch-link-open');
      expect(app.adapter.count('POST', '/vouch-links/lookup'), 0);
      expect(find.byKey(const Key('vouch-for-someone')), findsOneWidget);
    });

    test('takes the token from a pasted link, with or without the rest', () {
      expect(
        vouchTokenFrom('https://x.org/vouch/abcdefghij12'),
        'abcdefghij12',
      );
      expect(vouchTokenFrom(' /vouch/abcdefghij12/?a=1#b '), 'abcdefghij12');
      expect(vouchTokenFrom('abcdefghij12'), 'abcdefghij12');
      expect(vouchTokenFrom('short'), isNull);
      expect(vouchTokenFrom(''), isNull);
    });

    test('builds a link from the address of the API', () {
      expect(
        vouchLinkFor('tok', apiBase: 'https://demo.example.org/api/v1'),
        'https://demo.example.org/vouch/tok',
      );
      expect(
        vouchLinkFor('tok', apiBase: 'http://10.0.2.2:8000/api/v1'),
        'http://10.0.2.2:8000/vouch/tok',
      );
      expect(vouchLinkFor('tok', apiBase: ''), '/vouch/tok');
    });
  });

  group('where a person may go', () {
    PersonMe of(String status) => PersonMe.fromJson(personJson(status: status));

    test('a revoked person only has the home', () {
      final p = of('revoked');
      expect(personMayVisit(p, '/member'), isTrue);
      expect(personMayVisit(p, '/member/notifications'), isFalse);
      expect(personMayVisit(p, '/vouch/abcdefghij12'), isFalse);
    });

    test(
      'an applicant has the home and the notifications, nothing to vouch',
      () {
        final p = of('pending');
        expect(personMayVisit(p, '/member'), isTrue);
        expect(personMayVisit(p, '/member/notifications'), isTrue);
        expect(personMayVisit(p, '/member/vouches'), isFalse);
        expect(personMayVisit(p, '/vouch/abcdefghij12'), isFalse);
        expect(personMayVisit(p, '/freelancer/home'), isFalse);
      },
    );

    test(
      'an admitted person has the screens of a member and the vouch page',
      () {
        for (final status in ['searcher', 'provider', 'verifier']) {
          final p = of(status);
          expect(personMayVisit(p, '/member/vouches'), isTrue);
          expect(personMayVisit(p, '/member/notifications'), isTrue);
          expect(personMayVisit(p, '/vouch/abcdefghij12'), isTrue);
          expect(personMayVisit(p, '/freelancer/home'), isFalse);
        }
      },
    );
  });

  group('the vouches I gave', () {
    testWidgets('lists them and withdraws one that still can be', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, _emptyNotes))
            ..reply(
              'GET',
              '/me/vouches-given',
              FakeReply(200, {
                'items': [
                  {
                    'id': 'g1',
                    'applicant_name': 'Nadia Applicant',
                    'applicant_status': 'pending',
                    'requested_status': 'searcher',
                    'withdrawn': false,
                    'can_withdraw': true,
                    'created_at': '2026-11-13T08:00:00Z',
                  },
                  {
                    'id': 'g2',
                    'applicant_name': 'Sam Searcher',
                    'applicant_status': 'searcher',
                    'requested_status': null,
                    'withdrawn': false,
                    'can_withdraw': false,
                    'created_at': '2026-11-10T08:00:00Z',
                  },
                ],
              }),
            )
            ..reply('DELETE', '/vouches/g1', FakeReply(204));
        },
      );
      await tapKey(tester, 'vouches-given');
      expect(find.textContaining('Sam Searcher: decided'), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/me/vouches-given',
        FakeReply(200, {
          'items': [
            {
              'id': 'g1',
              'applicant_name': 'Nadia Applicant',
              'applicant_status': 'pending',
              'requested_status': 'searcher',
              'withdrawn': true,
              'can_withdraw': false,
              'created_at': '2026-11-13T08:00:00Z',
            },
          ],
        }),
      );
      await tester.tap(find.text('Withdraw my vouch for Nadia Applicant'));
      await tester.pumpAndSettle();
      expect(app.adapter.count('DELETE', '/vouches/g1'), 1);
      expect(find.textContaining('Nadia Applicant: withdrawn'), findsOneWidget);
      expect(find.textContaining('Withdraw my vouch'), findsNothing);
    });

    testWidgets('says when there is nothing', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, _emptyNotes))
            ..reply('GET', '/me/vouches-given', FakeReply(200, _noVouches));
        },
      );
      await tapKey(tester, 'vouches-given');
      expect(find.text('You have not vouched for anyone.'), findsOneWidget);
    });
  });

  group('notifications', () {
    final list = {
      'items': [
        {
          'id': 'n1',
          'kind': 'vouch_received',
          'subject': {'id': 'p1', 'name': 'Vera Voucher'},
          'created_at': '2026-11-13T09:00:00Z',
          'read': false,
        },
        {
          'id': 'n2',
          'kind': 'admitted',
          'subject': {'id': 'p2', 'name': 'Lena Leader'},
          'created_at': '2026-11-13T08:00:00Z',
          'read': true,
        },
        {
          'id': 'n3',
          'kind': 'applicant_new',
          'subject': {'id': 'p3', 'name': ''},
          'created_at': '2026-11-12T08:00:00Z',
          'read': false,
        },
        {
          'id': 'n4',
          'kind': 'something_new',
          'subject': null,
          'created_at': '2026-11-11T08:00:00Z',
          'read': true,
        },
      ],
      'total': 4,
      'unread_count': 2,
    };

    testWidgets('shows the count on the bell and a line for each kind', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply('GET', '/me/notifications', FakeReply(200, list));
        },
      );
      expect(find.byTooltip('Notifications (2 unread)'), findsOneWidget);
      await tapKey(tester, 'notifications');
      expect(
        find.textContaining('new · Vera Voucher vouched for you'),
        findsOneWidget,
      );
      expect(find.textContaining('Lena Leader admitted you'), findsOneWidget);
      expect(
        find.textContaining('new · Someone chose your home group'),
        findsOneWidget,
      );
      expect(find.textContaining('Something happened'), findsOneWidget);
    });

    testWidgets('marks one as read and then all', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter
            ..reply('GET', '/me/notifications', FakeReply(200, list))
            ..reply('POST', '/me/notifications/n1/read', FakeReply(204))
            ..reply('POST', '/me/notifications/read-all', FakeReply(204));
        },
      );
      await tapKey(tester, 'notifications');
      app.adapter.setReply(
        'GET',
        '/me/notifications',
        FakeReply(200, {...list, 'unread_count': 1}),
      );
      await tester.tap(find.text('Mark as read: Vera Voucher vouched for you'));
      await tester.pumpAndSettle();
      expect(app.adapter.count('POST', '/me/notifications/n1/read'), 1);
      app.adapter.setReply(
        'GET',
        '/me/notifications',
        FakeReply(200, {'items': [], 'total': 0, 'unread_count': 0}),
      );
      await tapKey(tester, 'read-all');
      expect(app.adapter.count('POST', '/me/notifications/read-all'), 1);
      expect(find.text('Nothing new.'), findsOneWidget);
      expect(find.byKey(const Key('read-all')), findsNothing);
    });

    testWidgets('shows an error with a retry when the list cannot load', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply(
            'GET',
            '/me/notifications',
            FakeReply(500, {
              'error': {'code': 'server_error', 'message': 'no'},
            }),
          );
        },
      );
      await tapKey(tester, 'notifications');
      expect(find.text('Try again'), findsOneWidget);
      app.adapter.setReply('GET', '/me/notifications', FakeReply(200, list));
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('new · Vera Voucher vouched for you'),
        findsOneWidget,
      );
    });

    testWidgets('are asked for again every minute while open', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _provider());
          adapter.reply(
            'GET',
            '/me/notifications',
            FakeReply(200, _emptyNotes),
          );
        },
      );
      expect(app.adapter.count('GET', '/me/notifications'), 1);
      await tester.pump(const Duration(seconds: 61));
      await tester.pumpAndSettle();
      expect(app.adapter.count('GET', '/me/notifications'), 2);
    });

    testWidgets('a revoked person has no bell and no request', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => signedInAsPerson(
          adapter,
          store,
          personJson(status: 'revoked', group: null, leader: null),
        ),
      );
      expect(find.byKey(const Key('notifications')), findsNothing);
      expect(app.adapter.count('GET', '/me/notifications'), 0);
    });
  });
}
