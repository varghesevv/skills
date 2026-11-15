import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/leader/leader_providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};
const _id = 'prov-1';

/// Not a real number; the server's answer in these tests.
final _number = '+9715${fresh('n').hashCode.abs() % 10000000}'.padRight(
  13,
  '0',
);

Map<String, Object?> _provider({Map<String, Object?>? mine, String id = _id}) =>
    {
      'id': id,
      'full_name': 'Anita Provider',
      'whatsapp_availability': true,
      'nationality': 'Examplean',
      'primary_language': 'English',
      'rate_per_hour': 45.5,
      'rate_currency': 'AED',
      'is_rate_negotiable': true,
      'labels': [
        {
          'label': {
            'id': 's1',
            'label_name': 'plumbing',
            'label_type': 'skill',
            'is_active': true,
          },
          'level': {
            'id': 'l1',
            'label_name': 'basic',
            'label_type': 'skill_level',
            'is_active': true,
          },
        },
        {
          'label': {
            'id': 'g1',
            'label_name': 'English',
            'label_type': 'language',
            'is_active': true,
          },
          'level': null,
        },
      ],
      'average_rating': 8.5,
      'rating_count': 4,
      'church': {'id': 'church-1', 'name': 'Grace Church'},
      'home_group': {'id': 'group-1', 'name': 'Riverside'},
      'unavailable': [
        {
          'id': 'u1',
          'unavailable_from': '2026-12-10T08:00:00Z',
          'unavailable_to': '2026-12-12T20:00:00Z',
        },
      ],
      'my_rating': mine,
    };

Map<String, Object?> _given(int score, {String? comment = 'Fine'}) => {
  'id': 'rt-1',
  'provider_id': _id,
  'provider_name': 'Anita Provider',
  'rating': score,
  'comment': comment,
  'rated_on': '2026-11-01T10:00:00Z',
  'updated_at': null,
};

Map<String, Object?> _ratings(int n) => {
  'items': [
    for (var i = 0; i < n; i++)
      {
        'rating': 9,
        'comment': 'Very good $i',
        'rated_on': '2026-11-01T10:00:00Z',
      },
  ],
  'total': n,
  'page': 1,
  'page_size': 10,
};

Map<String, Object?> _row() => {
  'id': _id,
  'full_name': 'Anita Provider',
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'nationality': 'Examplean',
  'primary_language': 'English',
  'whatsapp_availability': true,
  'rate_per_hour': 45.5,
  'rate_currency': 'AED',
  'is_rate_negotiable': true,
  'average_rating': 8.5,
  'rating_count': 4,
  'skills': [
    {'name': 'plumbing', 'level': 'basic'},
  ],
  'languages': ['English'],
  'timings': <Object?>[],
  'nativity': <Object?>[],
};

Future<TestApp> _open(
  WidgetTester tester, {
  String status = 'searcher',
  Map<String, Object?>? provider,
  void Function(FakeAdapter adapter)? arrange,
  List<String>? dialled,
}) async {
  final app = await pumpApp(
    tester,
    size: const Size(400, 3000),
    overrides: [
      dialerProvider.overrideWithValue((number) async {
        dialled?.add(number);
        return true;
      }),
    ],
    arrange: (adapter, store) {
      signedInAsPerson(
        adapter,
        store,
        personJson(status: status, requested: null),
      );
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply('GET', '/labels', FakeReply(200, <Object?>[]))
        ..reply('GET', '/churches', FakeReply(200, {'items': <Object?>[]}))
        ..reply(
          'GET',
          '/search/freelancers',
          FakeReply(200, {
            'items': [_row()],
            'total': 1,
            'page': 1,
            'page_size': 12,
          }),
        )
        ..reply(
          'GET',
          '/freelancers/$_id',
          FakeReply(200, provider ?? _provider()),
        )
        ..reply(
          'GET',
          '/freelancers/$_id/ratings',
          FakeReply(200, _ratings(2)),
        );
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'provider-search');
  await tester.tap(find.text('Anita Provider'));
  await tester.pumpAndSettle();
  return app;
}

void main() {
  test('the page may be opened by a searcher or above only', () {
    PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
    for (final status in [
      'searcher',
      'provider',
      'verifier',
      'admin',
      'owner',
    ]) {
      expect(
        personMayVisit(of(status), '/member/providers/x'),
        isTrue,
        reason: status,
      );
    }
    for (final status in ['pending', 'revoked']) {
      expect(
        personMayVisit(of(status), '/member/providers/x'),
        isFalse,
        reason: status,
      );
    }
  });

  group('the facts', () {
    testWidgets(
      'are shown, with the church, the labels and the time off, and no number',
      (tester) async {
        await _open(tester);
        expect(find.text('45.50 AED per hour · negotiable'), findsOneWidget);
        expect(find.text('Rated 8.5 by 4'), findsOneWidget);
        expect(find.text('Grace Church · Riverside'), findsOneWidget);
        expect(find.text('plumbing · basic'), findsOneWidget);
        expect(find.text('English'), findsWidgets);
        expect(find.textContaining('Very good 0'), findsOneWidget);
        expect(find.textContaining('+971'), findsNothing);
      },
    );

    testWidgets(
      'a provider sees their own page without the rating form and Reveal',
      (tester) async {
        await _open(
          tester,
          status: 'provider',
          provider: _provider(id: 'p1'),
          arrange: (a) => a
            ..setReply(
              'GET',
              '/search/freelancers',
              FakeReply(200, {
                'items': [
                  {..._row(), 'id': 'p1'},
                ],
                'total': 1,
                'page': 1,
                'page_size': 12,
              }),
            )
            ..setReply(
              'GET',
              '/freelancers/p1',
              FakeReply(200, _provider(id: 'p1')),
            )
            ..setReply(
              'GET',
              '/freelancers/p1/ratings',
              FakeReply(200, _ratings(0)),
            ),
        );
        expect(find.byKey(const Key('reveal')), findsNothing);
        expect(find.byKey(const Key('rating-save')), findsNothing);
      },
    );

    testWidgets('a failed load offers to try again', (tester) async {
      await _open(
        tester,
        arrange: (a) => a.setReply(
          'GET',
          '/freelancers/$_id',
          FakeReply(404, {
            'error': {
              'code': 'not_found',
              'message': 'no',
              'details': <String, Object?>{},
            },
          }),
        ),
      );
      expect(find.text('Try again'), findsOneWidget);
    });
  });

  group('Reveal', () {
    testWidgets(
      'asks only when pressed, keeps the number in the page and opens the dialler',
      (tester) async {
        final dialled = <String>[];
        final app = await _open(
          tester,
          dialled: dialled,
          arrange: (a) => a.reply(
            'POST',
            '/freelancers/$_id/reveal-mobile',
            FakeReply(200, {'mobile_number': _number}),
          ),
        );
        expect(find.text(_number), findsNothing);
        expect(app.adapter.count('POST', '/freelancers/$_id/reveal-mobile'), 0);
        await tester.tap(find.byKey(const Key('reveal')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('revealed-number')), findsOneWidget);
        expect(dialled, [_number]);
        final sent = app.adapter.seen.last;
        expect(sent.body, {
          'channel': 'dial',
          'source': 'detail',
          'searched_skills': <Object?>[],
        });
      },
    );

    testWidgets('says so when the limit is reached', (tester) async {
      await _open(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/freelancers/$_id/reveal-mobile',
          FakeReply(429, {
            'error': {
              'code': 'reveal_limit_reached',
              'message': 'no',
              'details': <String, Object?>{},
            },
          }),
        ),
      );
      await tester.tap(find.byKey(const Key('reveal')));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('revealed many numbers recently'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('revealed-number')), findsNothing);
      expect(find.byKey(const Key('reveal')), findsOneWidget); // can try again
    });
  });

  group('rating', () {
    testWidgets('a score is needed before anything is sent', (tester) async {
      final app = await _open(tester);
      await tester.tap(find.byKey(const Key('rating-save')));
      await tester.pumpAndSettle();
      expect(find.text('Choose a score.'), findsOneWidget);
      expect(app.adapter.count('POST', '/ratings'), 0);
    });

    testWidgets('gives a rating with a score and a comment', (tester) async {
      final app = await _open(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/ratings',
          FakeReply(201, _given(8, comment: 'Great')),
        ),
      );
      await tester.tap(find.byKey(const Key('rating-score')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('8').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('rating-comment')), 'Great');
      await tester.tap(find.byKey(const Key('rating-save')));
      await tester.pumpAndSettle();
      expect(app.adapter.seen.lastWhere((r) => r.path == '/ratings').body, {
        'provider_id': _id,
        'rating': 8,
        'comment': 'Great',
      });
      expect(find.text('Saved.'), findsOneWidget);
    });

    testWidgets('changes the rating already given, through PUT', (
      tester,
    ) async {
      final app = await _open(
        tester,
        provider: _provider(mine: _given(7)),
        arrange: (a) =>
            a.reply('PUT', '/ratings/rt-1', FakeReply(200, _given(9))),
      );
      expect(find.text('Change your rating'), findsOneWidget);
      await tester.tap(find.byKey(const Key('rating-score')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('9').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('rating-save')));
      await tester.pumpAndSettle();
      expect(app.adapter.count('PUT', '/ratings/rt-1'), 1);
      expect(app.adapter.count('POST', '/ratings'), 0);
    });

    testWidgets('says so when the provider was already rated', (tester) async {
      await _open(
        tester,
        arrange: (a) => a.reply(
          'POST',
          '/ratings',
          FakeReply(409, {
            'error': {
              'code': 'already_rated',
              'message': 'no',
              'details': <String, Object?>{},
            },
          }),
        ),
      );
      await tester.tap(find.byKey(const Key('rating-score')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('5').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('rating-save')));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'You already rated this freelancer. Open your rating to change it.',
        ),
        findsOneWidget,
      );
      expect(find.text('Saved.'), findsNothing);
    });
  });
}
