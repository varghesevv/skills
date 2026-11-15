import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};
const _path = '/search/freelancers';

Map<String, Object?> _label(String id, String name, String type) => {
  'id': id,
  'label_name': name,
  'label_type': type,
  'is_active': true,
};

final _labels = [
  _label('s1', 'plumbing', 'skill'),
  _label('s2', 'carpentry', 'skill'),
  _label('l1', 'basic', 'skill_level'),
  _label('g1', 'English', 'language'),
];

Map<String, Object?> _result(int n, {String id = ''}) => {
  'id': id.isEmpty ? 'r$n' : id,
  'full_name': 'Provider $n',
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'nationality': 'Examplean',
  'primary_language': 'English',
  'whatsapp_availability': true,
  'rate_per_hour': 30.0,
  'rate_currency': 'AED',
  'is_rate_negotiable': n.isEven,
  'average_rating': n == 1 ? null : 8.5,
  'rating_count': n == 1 ? 0 : 4,
  'skills': [
    {'name': 'plumbing', 'level': 'basic'},
  ],
  'languages': ['English'],
  'timings': <Object?>[],
  'nativity': <Object?>[],
};

Map<String, Object?> _page(
  int from,
  int count, {
  required int total,
  int page = 1,
}) => {
  'items': [for (var i = from; i < from + count; i++) _result(i)],
  'total': total,
  'page': page,
  'page_size': 12,
};

Future<TestApp> _open(
  WidgetTester tester, {
  String status = 'searcher',
  FakeReply? first,
  void Function(FakeAdapter adapter)? arrange,
  Size size = const Size(400, 3000),
}) async {
  final app = await pumpApp(
    tester,
    size: size,
    arrange: (adapter, store) {
      signedInAsPerson(
        adapter,
        store,
        personJson(status: status, requested: null),
      );
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply('GET', '/labels', FakeReply(200, _labels))
        ..reply(
          'GET',
          '/churches',
          FakeReply(200, {
            'items': [
              {'id': 'church-1', 'name': 'Grace Church'},
              {'id': 'church-2', 'name': 'Hope Church'},
            ],
          }),
        )
        ..reply(
          'GET',
          '/churches/church-2/home-groups',
          FakeReply(200, {
            'items': [
              {'id': 'group-9', 'name': 'Harbour', 'leader_name': 'Hal'},
            ],
          }),
        )
        ..reply('GET', _path, first ?? FakeReply(200, _page(1, 2, total: 2)));
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'provider-search');
  return app;
}

SeenRequest _last(TestApp app) =>
    app.adapter.seen.lastWhere((r) => r.path == _path);

void main() {
  group('who may search', () {
    for (final status in [
      'searcher',
      'provider',
      'verifier',
      'admin',
      'owner',
    ]) {
      testWidgets('a $status finds the tile and the results', (tester) async {
        await _open(tester, status: status);
        expect(find.text('Provider 1'), findsOneWidget);
      });
    }

    testWidgets('an applicant has no tile', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, personJson(status: 'pending'));
          adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
        },
      );
      expect(find.byKey(const Key('provider-search')), findsNothing);
    });

    test('only a searcher or above may open the address', () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final status in [
        'searcher',
        'provider',
        'verifier',
        'admin',
        'owner',
      ]) {
        expect(
          personMayVisit(of(status), '/member/search'),
          isTrue,
          reason: status,
        );
      }
      for (final status in ['pending', 'revoked']) {
        expect(
          personMayVisit(of(status), '/member/search'),
          isFalse,
          reason: status,
        );
      }
    });
  });

  group('the results', () {
    testWidgets(
      'show the church, the group, the rate and the rating, and no number',
      (tester) async {
        await _open(tester);
        expect(find.text('Grace Church · Riverside'), findsNWidgets(2));
        expect(find.text('30 AED per hour'), findsOneWidget);
        expect(find.text('Not rated yet'), findsOneWidget);
        expect(find.textContaining('+971'), findsNothing);
        expect(find.text('plumbing · basic'), findsNWidgets(2));
      },
    );

    testWidgets(
      'say so when no one matches, and clear the filters from there',
      (tester) async {
        final app = await _open(
          tester,
          first: FakeReply(200, {
            'items': [],
            'total': 0,
            'page': 1,
            'page_size': 12,
          }),
        );
        expect(find.text('No one matches.'), findsOneWidget);
        expect(
          find.byKey(const Key('clear-all')),
          findsNothing,
        ); // nothing to clear yet
        expect(app.adapter.count('GET', _path), 1);
      },
    );

    testWidgets('the person themselves is marked and gets no other change', (
      tester,
    ) async {
      await _open(
        tester,
        status: 'provider',
        first: FakeReply(200, {
          'items': [_result(1, id: 'p1')],
          'total': 1,
          'page': 1,
          'page_size': 12,
        }),
      );
      expect(find.text('This is you.'), findsOneWidget);
    });

    testWidgets('come twelve at a time, with Show more', (tester) async {
      final app = await _open(
        tester,
        first: FakeReply(200, _page(1, 12, total: 14)),
        arrange: (a) => a.reply(
          'GET',
          _path,
          FakeReply(200, _page(13, 2, total: 14, page: 2)),
        ),
      );
      expect(find.byKey(const Key('show-more')), findsOneWidget);
      await tapKey(tester, 'show-more');
      expect(find.text('Provider 14'), findsOneWidget);
      expect(find.byKey(const Key('show-more')), findsNothing);
      expect(
        app.adapter.seen
            .where((r) => r.path == _path)
            .map((r) => r.query['page']),
        [1, 2],
      );
    });

    testWidgets('offer a retry when they cannot be loaded', (tester) async {
      final app = await _open(
        tester,
        first: FakeReply(500, {
          'error': {
            'code': 'server_error',
            'message': 'no',
            'details': <String, Object?>{},
          },
        }),
      );
      expect(find.text('Try again'), findsOneWidget);
      app.adapter.setReply('GET', _path, FakeReply(200, _page(1, 2, total: 2)));
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Provider 1'), findsOneWidget);
    });
  });

  group('the filters', () {
    testWidgets('search by name sends the name and shows it as a chip', (
      tester,
    ) async {
      final app = await _open(tester);
      await tester.enterText(find.byKey(const Key('search-name')), 'anita');
      await tapKey(tester, 'search-go');
      expect(_last(app).query['name'], 'anita');
      expect(find.byKey(const Key('chip-name')), findsOneWidget);
    });

    testWidgets('a removed chip is taken off the request', (tester) async {
      final app = await _open(tester);
      await tester.enterText(find.byKey(const Key('search-name')), 'anita');
      await tapKey(tester, 'search-go');
      await tester.tap(find.byTooltip('anita'));
      await tester.pumpAndSettle();
      expect(_last(app).query.containsKey('name'), isFalse);
    });

    testWidgets('skills, level, rate and currency go to the API when applied', (
      tester,
    ) async {
      final app = await _open(tester);
      await tapKey(tester, 'open-filters');
      await tapKey(tester, 'skill-plumbing');
      await tapKey(tester, 'skill-carpentry');
      await tapKey(tester, 'match-all');
      await tester.enterText(find.byKey(const Key('max-rate')), '60');
      await tester.enterText(find.byKey(const Key('currency')), 'aed');
      await tapKey(tester, 'apply-filters');
      final query = _last(app).query;
      expect(query['skill'], ['plumbing', 'carpentry']);
      expect(query['skill_match'], 'all');
      expect(query['max_rate'], '60');
      expect(query['currency'], 'AED');
      expect(find.byKey(const Key('chip-skill-plumbing')), findsOneWidget);
    });

    testWidgets('a rate without a currency is explained and not sent', (
      tester,
    ) async {
      final app = await _open(tester);
      final before = app.adapter.count('GET', _path);
      await tapKey(tester, 'open-filters');
      await tester.enterText(find.byKey(const Key('max-rate')), '60');
      await tapKey(tester, 'apply-filters');
      expect(find.text('Add the currency for this rate.'), findsOneWidget);
      expect(app.adapter.count('GET', _path), before);
    });

    testWidgets('a church and its group narrow the search', (tester) async {
      final app = await _open(tester);
      await tapKey(tester, 'open-filters');
      await tester.dragUntilVisible(
        find.byKey(const Key('church')),
        find.byType(ListView).last,
        const Offset(0, -200),
      );
      await tester.tap(find.byKey(const Key('church')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Hope Church').last);
      await tester.pumpAndSettle();
      await tester.dragUntilVisible(
        find.byKey(const Key('group')),
        find.byType(ListView).last,
        const Offset(0, -200),
      );
      await tester.tap(find.byKey(const Key('group')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Harbour').last);
      await tester.pumpAndSettle();
      await tester.dragUntilVisible(
        find.byKey(const Key('apply-filters')),
        find.byType(ListView).last,
        const Offset(0, -200),
      );
      await tapKey(tester, 'apply-filters');
      final query = _last(app).query;
      expect(query['church_id'], 'church-2');
      expect(query['home_group_id'], 'group-9');
    });

    testWidgets('the sort goes to the API', (tester) async {
      final app = await _open(tester);
      await tester.tap(find.byKey(const Key('sort')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Best rated').last);
      await tester.pumpAndSettle();
      expect(_last(app).query['sort'], 'rating');
    });

    testWidgets('clear all removes the filters but keeps the sort', (
      tester,
    ) async {
      final app = await _open(tester);
      await tester.tap(find.byKey(const Key('sort')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Lowest rate').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'open-filters');
      await tapKey(tester, 'skill-plumbing');
      await tapKey(tester, 'apply-filters');
      expect(_last(app).query['skill'], ['plumbing']);
      await tapKey(tester, 'open-filters');
      await tapKey(tester, 'clear-filters');
      final query = _last(app).query;
      expect(query.containsKey('skill'), isFalse);
      expect(query['sort'], 'rate');
    });
  });
}
