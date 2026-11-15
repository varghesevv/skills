import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/core/session/session_controller.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

const _tiles = [
  'provider-profile',
  'provider-skills',
  'provider-availability',
  'provider-ratings',
];

Map<String, Object?> _profile() => {
  'id': 'p1',
  'full_name': 'Pat Provider',
  'email': 'pat@example.test',
  'mobile_number': '+971501234567',
  'whatsapp_availability': true,
  'nationality': 'Examplean',
  'primary_language': 'English',
  'rate_per_hour': 30.0,
  'rate_currency': 'AED',
  'is_rate_negotiable': false,
  'labels': <Object?>[],
  'created_at': '2026-10-01T10:00:00Z',
};

Future<TestApp> _open(
  WidgetTester tester,
  String status, {
  void Function(FakeAdapter adapter)? arrange,
}) => pumpApp(
  tester,
  arrange: (adapter, store) {
    signedInAsPerson(
      adapter,
      store,
      personJson(status: status, requested: null),
    );
    adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
    arrange?.call(adapter);
  },
);

void main() {
  group('who has the provider pages', () {
    for (final status in ['provider', 'verifier', 'admin', 'owner']) {
      testWidgets('a $status finds the four pages on the home', (tester) async {
        await _open(tester, status);
        for (final key in _tiles) {
          expect(find.byKey(Key(key)), findsOneWidget, reason: key);
        }
      });
    }

    testWidgets('a searcher has none', (tester) async {
      await _open(tester, 'searcher');
      for (final key in _tiles) {
        expect(find.byKey(Key(key)), findsNothing, reason: key);
      }
    });

    test('only a provider or above may open the addresses', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final path in [
        '/member/profile',
        '/member/skills',
        '/member/availability',
        '/member/ratings',
      ]) {
        for (final status in ['provider', 'verifier', 'admin', 'owner']) {
          expect(
            personMayVisit(of(status), path),
            isTrue,
            reason: '$status $path',
          );
        }
        for (final status in ['pending', 'revoked', 'searcher']) {
          expect(
            personMayVisit(of(status), path),
            isFalse,
            reason: '$status $path',
          );
        }
      }
    });
  });

  group('the pages', () {
    testWidgets(
      'the profile is the person\'s own, through the unchanged path',
      (tester) async {
        final app = await _open(
          tester,
          'provider',
          arrange: (a) =>
              a.reply('GET', '/freelancers/me', FakeReply(200, _profile())),
        );
        await tapKey(tester, 'provider-profile');
        expect(find.text('Pat Provider'), findsWidgets);
        expect(app.adapter.count('GET', '/freelancers/me'), 1);
      },
    );

    testWidgets('the ratings are asked for with the person\'s own id', (
      tester,
    ) async {
      final app = await _open(
        tester,
        'provider',
        arrange: (a) => a.reply(
          'GET',
          '/freelancers/p1/ratings',
          FakeReply(200, {
            'items': [
              {
                'rating': 9,
                'comment': 'Very good',
                'rated_on': '2026-11-01T10:00:00Z',
              },
            ],
            'total': 1,
            'page': 1,
            'page_size': 10,
          }),
        ),
      );
      await tapKey(tester, 'provider-ratings');
      expect(find.text('Very good'), findsOneWidget);
      expect(app.adapter.count('GET', '/freelancers/p1/ratings'), 1);
    });

    testWidgets('a refresh of the person does not reload the ratings', (
      tester,
    ) async {
      final app = await _open(
        tester,
        'provider',
        arrange: (a) => a.reply(
          'GET',
          '/freelancers/p1/ratings',
          FakeReply(200, {
            'items': [
              {
                'rating': 7,
                'comment': 'Fine',
                'rated_on': '2026-11-01T10:00:00Z',
              },
            ],
            'total': 1,
            'page': 1,
            'page_size': 10,
          }),
        ),
      );
      await tapKey(tester, 'provider-ratings');
      expect(app.adapter.count('GET', '/freelancers/p1/ratings'), 1);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(Scaffold).first),
      );
      unawaited(container.read(sessionProvider.notifier).refreshPerson());
      await tester.pumpAndSettle();
      expect(app.adapter.count('GET', '/freelancers/p1/ratings'), 1);
      expect(find.text('Fine'), findsOneWidget);
    });

    testWidgets('the availability lists the periods', (tester) async {
      await _open(
        tester,
        'verifier',
        arrange: (a) => a.reply(
          'GET',
          '/freelancers/me/unavailability',
          FakeReply(200, <Object?>[]),
        ),
      );
      await tapKey(tester, 'provider-availability');
      expect(find.byKey(const Key('add-period')), findsOneWidget);
    });

    testWidgets('the skills and labels open', (tester) async {
      await _open(
        tester,
        'owner',
        arrange: (a) => a
          ..reply('GET', '/freelancers/me', FakeReply(200, _profile()))
          ..reply('GET', '/labels', FakeReply(200, <Object?>[])),
      );
      await tapKey(tester, 'provider-skills');
      expect(find.text('Skills and labels'), findsWidgets);
    });
  });
}
