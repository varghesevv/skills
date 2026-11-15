import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _given(int n) => {
  'id': 'r$n',
  'provider_id': 'p$n',
  'provider_name': 'Provider $n',
  'rating': 8,
  'comment': 'Comment $n',
  'rated_on': '2026-11-01T10:00:00Z',
};

Map<String, Object?> _page(List<int> ns, int total, int page) => {
  'items': [for (final n in ns) _given(n)],
  'total': total,
  'page': page,
  'page_size': 10,
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
  test('the ratings given need a searcher; the account too (an applicant edits on their own page)', () {
    PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
    for (final s in ['searcher', 'provider', 'verifier', 'admin', 'owner']) {
      expect(personMayVisit(of(s), '/member/ratings-given'), isTrue, reason: s);
    }
    for (final s in ['pending', 'revoked']) {
      expect(personMayVisit(of(s), '/member/ratings-given'), isFalse);
    }
    for (final s in ['searcher', 'provider', 'owner']) {
      expect(personMayVisit(of(s), '/member/account'), isTrue, reason: s);
    }
    for (final s in ['pending', 'revoked']) {
      expect(personMayVisit(of(s), '/member/account'), isFalse);
    }
  });

  testWidgets('the ratings given are shown ten at a time', (tester) async {
    final app = await _open(
      tester,
      'searcher',
      arrange: (a) {
        a.reply(
          'GET',
          '/workhosts/me/ratings',
          FakeReply(200, _page([1, 2], 3, 1)),
        );
        a.reply(
          'GET',
          '/workhosts/me/ratings',
          FakeReply(200, _page([3], 3, 2)),
        );
      },
    );
    await tapKey(tester, 'ratings-given');
    expect(find.text('Provider 1'), findsOneWidget);
    expect(app.adapter.seen.last.query['page'], 1);
    await tapKey(tester, 'show-more');
    expect(find.text('Provider 3'), findsOneWidget);
    expect(find.byKey(const Key('show-more')), findsNothing);
    expect(app.adapter.seen.last.query['page'], 2);
  });

  testWidgets('an empty list says so', (tester) async {
    await _open(
      tester,
      'searcher',
      arrange: (a) => a.reply(
        'GET',
        '/workhosts/me/ratings',
        FakeReply(200, _page([], 0, 1)),
      ),
    );
    await tapKey(tester, 'ratings-given');
    expect(find.text('You have not rated anyone yet.'), findsOneWidget);
  });

  testWidgets('saving the account sends name and mobile to PUT /me', (
    tester,
  ) async {
    final app = await _open(
      tester,
      'searcher',
      arrange: (a) => a.reply(
        'PUT',
        '/me',
        FakeReply(200, personJson(status: 'searcher', requested: null)),
      ),
    );
    await tapKey(tester, 'account');
    await tester.enterText(find.byKey(const Key('account-name')), 'New Name');
    await tapKey(tester, 'account-save');
    final put = app.adapter.seen.lastWhere((r) => r.method == 'PUT');
    expect((put.body as Map)['full_name'], 'New Name');
    expect(find.text('Saved.'), findsOneWidget);
  });

  testWidgets('a bad name is refused before anything is sent', (tester) async {
    final app = await _open(tester, 'searcher');
    await tapKey(tester, 'account');
    await tester.enterText(find.byKey(const Key('account-name')), '');
    await tapKey(tester, 'account-save');
    expect(app.adapter.count('PUT', '/me'), 0);
  });

  testWidgets('a number that is taken is explained', (tester) async {
    await _open(
      tester,
      'searcher',
      arrange: (a) => a.reply(
        'PUT',
        '/me',
        FakeReply(409, {
          'error': {'code': 'account_exists', 'message': 'x'},
        }),
      ),
    );
    await tapKey(tester, 'account');
    await tapKey(tester, 'account-save');
    expect(
      find.text('This mobile number belongs to another account.'),
      findsOneWidget,
    );
  });

  testWidgets('the list shows progress while it loads', (tester) async {
    final hold = Completer<void>();
    await _open(
      tester,
      'searcher',
      arrange: (a) => a.reply(
        'GET',
        '/workhosts/me/ratings',
        FakeReply(200, _page([1], 1, 1), const {}, hold.future),
      ),
    );
    await tester.tap(find.byKey(const Key('ratings-given')));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byType(CircularProgressIndicator), findsWidgets);
    hold.complete();
    await tester.pumpAndSettle();
    expect(find.text('Provider 1'), findsOneWidget);
  });

  testWidgets('a failed list can be tried again', (tester) async {
    final app = await _open(
      tester,
      'searcher',
      arrange: (a) => a.reply(
        'GET',
        '/workhosts/me/ratings',
        FakeReply(500, {
          'error': {'code': 'server_error', 'message': 'x'},
        }),
      ),
    );
    await tapKey(tester, 'ratings-given');
    expect(find.text('Provider 1'), findsNothing);
    app.adapter.setReply(
      'GET',
      '/workhosts/me/ratings',
      FakeReply(200, _page([1], 1, 1)),
    );
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('Provider 1'), findsOneWidget);
  });

  testWidgets('a failed Show more keeps the list and the button', (
    tester,
  ) async {
    await _open(
      tester,
      'searcher',
      arrange: (a) {
        a.reply(
          'GET',
          '/workhosts/me/ratings',
          FakeReply(200, _page([1, 2], 3, 1)),
        );
        a.reply(
          'GET',
          '/workhosts/me/ratings',
          FakeReply(500, {
            'error': {'code': 'server_error', 'message': 'x'},
          }),
        );
      },
    );
    await tapKey(tester, 'ratings-given');
    await tapKey(tester, 'show-more');
    expect(find.text('Provider 1'), findsOneWidget);
    expect(
      find.text('Something went wrong. Please try again.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('show-more')), findsOneWidget);
  });

  for (final key in ['ratings-given', 'account']) {
    testWidgets('$key fits at double text size', (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await _open(
        tester,
        'searcher',
        arrange: (a) => a.reply(
          'GET',
          '/workhosts/me/ratings',
          FakeReply(200, _page([1, 2], 2, 1)),
        ),
      );
      await tapKey(tester, key);
      expect(tester.takeException(), isNull);
    });
  }
}
