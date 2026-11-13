import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _searcher({String? requested, int vouches = 0}) =>
    personJson(
      status: 'searcher',
      requested: requested,
      vouches: vouches,
      name: 'Sam Searcher',
    );

void _quiet(FakeAdapter adapter) => adapter
  ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
  ..reply(
    'GET',
    '/me/vouch-link',
    FakeReply(200, {'active': false, 'expires_at': null}),
  )
  ..reply('GET', '/me/vouches', FakeReply(200, {'items': []}));

void main() {
  group('applying to offer skills', () {
    testWidgets('a searcher who has not asked is offered the request', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher());
          _quiet(adapter);
        },
      );
      expect(find.text('Offer your skills'), findsOneWidget);
      expect(find.byKey(const Key('apply-provider')), findsOneWidget);
      expect(find.byKey(const Key('make-vouch-link')), findsNothing);
    });

    for (final status in ['provider', 'verifier', 'admin', 'owner']) {
      testWidgets('nobody who is a $status is offered it', (tester) async {
        await pumpApp(
          tester,
          arrange: (adapter, store) {
            signedInAsPerson(adapter, store, personJson(status: status));
            _quiet(adapter);
          },
        );
        expect(find.byKey(const Key('apply-provider')), findsNothing);
        expect(find.text('Offer your skills'), findsNothing);
      });
    }

    testWidgets('asking shows the request, the vouch link and the vouches', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher());
          _quiet(adapter);
          adapter.reply(
            'POST',
            '/me/apply-provider',
            FakeReply(200, _searcher(requested: 'provider')),
          );
        },
      );
      await tapKey(tester, 'apply-provider');
      expect(app.adapter.count('POST', '/me/apply-provider'), 1);
      expect(find.text('Your request'), findsOneWidget);
      expect(find.textContaining('You have 0 vouches so far'), findsOneWidget);
      expect(find.byKey(const Key('apply-provider')), findsNothing);
      expect(find.byKey(const Key('make-vouch-link')), findsOneWidget);
      // They are still a searcher, with the home of one.
      expect(find.text('Welcome, Sam Searcher'), findsOneWidget);
    });

    testWidgets('says how many vouches the request has', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(
            adapter,
            store,
            _searcher(requested: 'provider', vouches: 1),
          );
          _quiet(adapter);
        },
      );
      expect(find.textContaining('You have 1 vouch so far'), findsOneWidget);
    });

    testWidgets('says so when the status changed meanwhile', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher());
          _quiet(adapter);
          adapter.reply(
            'POST',
            '/me/apply-provider',
            FakeReply(409, {
              'error': {'code': 'not_searcher', 'message': 'no'},
            }),
          );
        },
      );
      await tapKey(tester, 'apply-provider');
      expect(find.textContaining('status changed meanwhile'), findsOneWidget);
      expect(find.byKey(const Key('apply-provider')), findsOneWidget);
    });

    testWidgets('shows another failure and lets them try again', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher());
          _quiet(adapter);
          adapter.reply(
            'POST',
            '/me/apply-provider',
            FakeReply(503, {
              'error': {'code': 'service_unavailable', 'message': 'down'},
            }),
          );
        },
      );
      await tapKey(tester, 'apply-provider');
      expect(find.byKey(const Key('apply-provider')), findsOneWidget);
      app.adapter.setReply(
        'POST',
        '/me/apply-provider',
        FakeReply(200, _searcher(requested: 'provider')),
      );
      await tapKey(tester, 'apply-provider');
      expect(find.text('Your request'), findsOneWidget);
    });
  });

  group('when somebody else changes it', () {
    testWidgets('a pull on the home asks who they are again', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher(requested: 'provider'));
          _quiet(adapter);
        },
      );
      expect(app.adapter.count('GET', '/me'), 1);
      app.adapter.setReply('GET', '/me', FakeReply(200, _searcher()));
      await tester.drag(find.byType(ListView).first, const Offset(0, 400));
      await tester.pumpAndSettle();
      expect(app.adapter.count('GET', '/me'), 2);
      expect(find.byKey(const Key('apply-provider')), findsOneWidget);
    });

    testWidgets('a new notification refreshes the page without a pull', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher(requested: 'provider'));
          _quiet(adapter);
        },
      );
      expect(find.text('Your request'), findsOneWidget);
      // The leader declines; the next poll carries the notice.
      app.adapter
        ..setReply('GET', '/me', FakeReply(200, _searcher()))
        ..setReply(
          'GET',
          '/me/notifications',
          FakeReply(200, {
            'items': [
              {
                'id': 'n1',
                'kind': 'provider_declined',
                'subject': {'id': 'p1', 'name': 'Lena Leader'},
                'created_at': '2026-11-13T09:00:00Z',
                'read': false,
              },
            ],
            'total': 1,
            'unread_count': 1,
          }),
        );
      await tester.pump(const Duration(seconds: 61));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('apply-provider')), findsOneWidget);
      expect(find.text('Your request'), findsNothing);
      await tapKey(tester, 'notifications');
      expect(
        find.textContaining(
          'Lena Leader declined your request to offer your skills',
        ),
        findsWidgets,
      );
    });

    testWidgets('a first answer with unread notices does not ask again', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _searcher());
          _quiet(adapter);
          adapter.setReply(
            'GET',
            '/me/notifications',
            FakeReply(200, {
              'items': [
                {
                  'id': 'n1',
                  'kind': 'admitted',
                  'subject': {'id': 'p1', 'name': 'Lena Leader'},
                  'created_at': '2026-11-13T09:00:00Z',
                  'read': false,
                },
              ],
              'total': 1,
              'unread_count': 1,
            }),
          );
        },
      );
      expect(app.adapter.count('GET', '/me'), 1);
    });

    testWidgets('a leader sees a request in the notices', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, personJson(status: 'verifier'));
          _quiet(adapter);
          adapter.setReply(
            'GET',
            '/me/notifications',
            FakeReply(200, {
              'items': [
                {
                  'id': 'n1',
                  'kind': 'provider_application',
                  'subject': {'id': 'p1', 'name': 'Sam Searcher'},
                  'created_at': '2026-11-13T09:00:00Z',
                  'read': false,
                },
              ],
              'total': 1,
              'unread_count': 1,
            }),
          );
        },
      );
      await tapKey(tester, 'notifications');
      expect(
        find.textContaining('Sam Searcher asks to offer their skills'),
        findsWidgets,
      );
    });
  });
}
