import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/providers.dart';
import 'package:skills_app/features/freelancer/ratings/ratings_controller.dart';
import 'package:skills_app/core/api/paged.dart';
import 'package:skills_app/core/format.dart';
import 'package:skills_app/features/freelancer/data/received_rating.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

Map<String, Object?> rating(
  int score, {
  String? comment,
  String day = '2026-10-20',
}) => {'rating': score, 'comment': comment, 'rated_on': '${day}T10:00:00Z'};

Map<String, Object?> page(
  List<Map<String, Object?>> items, {
  required int total,
  int number = 1,
}) => {'items': items, 'total': total, 'page': number, 'page_size': 10};

List<Map<String, Object?>> ratings(int count, {int from = 0}) => [
  for (var i = from; i < from + count; i++)
    rating(1 + i % 10, comment: i.isEven ? 'Comment $i' : null),
];

const path = '/freelancers/u1/ratings'; // the test account's id is u1

Future<TestApp> openRatings(
  WidgetTester tester, {
  required FakeReply first,
  List<FakeReply> more = const [],
  Map<String, String> words = defaultWords,
  // Tall by default, so every card of a page is built (a list only builds what is on screen).
  Size size = const Size(400, 4000),
  double textScale = 1.0,
}) async {
  final app = await pumpApp(
    tester,
    words: words,
    size: size,
    textScale: textScale,
    arrange: (adapter, store) {
      signedInAs(adapter, store, 'freelancer');
      adapter.reply('GET', path, first);
      for (final reply in more) {
        adapter.reply('GET', path, reply);
      }
    },
  );
  await tapTab(tester, 'My ratings');
  return app;
}

Finder get showMore => find.byKey(const Key('show-more'));

void main() {
  group('models', () {
    test('a rating is read with its day in UTC and an optional comment', () {
      final read = ReceivedRating.fromJson(
        rating(8, comment: 'Good', day: '2026-10-20'),
      );
      expect(read.rating, 8);
      expect(read.comment, 'Good');
      expect(read.ratedOn, DateTime.utc(2026, 10, 20, 10));
      expect(ReceivedRating.fromJson(rating(3)).comment, isNull);
    });

    test('a page keeps its numbers', () {
      final paged = Paged.fromJson(
        page(ratings(2), total: 12, number: 3),
        ReceivedRating.fromJson,
      );
      expect(paged.items, hasLength(2));
      expect([paged.total, paged.page, paged.pageSize], [12, 3, 10]);
    });
  });

  group('navigation', () {
    testWidgets('a freelancer has a ratings tab and a dashboard shortcut', (
      tester,
    ) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'freelancer'));
      expect(
        find.descendant(
          of: find.byType(NavigationBar),
          matching: find.text('My ratings'),
        ),
        findsOneWidget,
      );
      expect(find.text('My ratings'), findsNWidgets(2));
    });

    testWidgets('other roles do not have it', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'workhost'));
      expect(find.text('My ratings'), findsNothing);
    });
  });

  group('ratings screen', () {
    testWidgets('says so when nobody has rated yet', (tester) async {
      await openRatings(tester, first: FakeReply(200, page([], total: 0)));
      expect(find.text('You have not been rated yet.'), findsOneWidget);
      expect(find.textContaining('rating(s)'), findsNothing);
      expect(showMore, findsNothing);
    });

    testWidgets(
      'shows score, comment, a note when there is none, the day and the count',
      (tester) async {
        await openRatings(
          tester,
          first: FakeReply(
            200,
            page([
              rating(8, comment: 'Reliable and kind'),
              rating(3, day: '2026-09-02'),
            ], total: 2),
          ),
        );
        expect(find.text('2 rating(s)'), findsOneWidget);
        expect(find.text('8 out of 10'), findsOneWidget);
        expect(find.text('Reliable and kind'), findsOneWidget);
        expect(find.text('3 out of 10'), findsOneWidget);
        expect(find.text('No comment.'), findsOneWidget);
        expect(
          find.text(formatDay(DateTime.utc(2026, 9, 2, 10))),
          findsOneWidget,
        );
        expect(showMore, findsNothing); // everything is shown
      },
    );

    testWidgets('asks for ten at a time, for the signed-in freelancer', (
      tester,
    ) async {
      final app = await openRatings(
        tester,
        first: FakeReply(200, page(ratings(10), total: 23)),
      );
      final request = app.adapter.seen.firstWhere((r) => r.path == path);
      expect(request.query, {'page': 1, 'page_size': 10});
      expect(find.text('Showing 10 of 23'), findsOneWidget);
    });

    testWidgets(
      '"Show more" adds the next page and goes away when all are shown',
      (tester) async {
        final app = await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 12)),
          more: [
            FakeReply(200, page(ratings(2, from: 10), total: 12, number: 2)),
          ],
        );
        await tapKey(tester, 'show-more');
        final requests = app.adapter.seen.where((r) => r.path == path).toList();
        expect(requests.map((r) => r.query['page']), [1, 2]);
        expect(find.text('Comment 10'), findsOneWidget);
        expect(
          find.text('Comment 0'),
          findsOneWidget,
        ); // the first page is still there
        expect(showMore, findsNothing);
        expect(find.textContaining('Showing'), findsNothing);
      },
    );

    testWidgets('a second tap while loading does not ask twice', (
      tester,
    ) async {
      final gate = Completer<void>();
      final app = await openRatings(
        tester,
        first: FakeReply(200, page(ratings(10), total: 30)),
        more: [
          FakeReply(
            200,
            page(ratings(10, from: 10), total: 30, number: 2),
            const {},
            gate.future,
          ),
        ],
      );
      await tester.scrollUntilVisible(
        showMore,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(showMore);
      await tester.pump();
      await tester.pump();
      expect(showMore, findsNothing); // replaced by the spinner
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      gate.complete();
      await tester.pumpAndSettle();
      expect(
        app.adapter.seen.where((r) => r.path == path && r.query['page'] == 2),
        hasLength(1),
      );
    });

    testWidgets(
      'a failed "Show more" keeps the ratings, shows the message and can be repeated',
      (tester) async {
        final app = await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 12)),
          more: [FakeReply(503, apiError('service_unavailable'))],
        );
        await tapKey(tester, 'show-more');
        expect(
          find.text(
            'The service is temporarily unavailable. Please try again soon.',
          ),
          findsOneWidget,
        );
        expect(find.text('Comment 0'), findsOneWidget);
        expect(showMore, findsOneWidget);
        app.adapter.setReply(
          'GET',
          path,
          FakeReply(200, page(ratings(2, from: 10), total: 12, number: 2)),
        );
        await tapKey(tester, 'show-more');
        expect(
          find.text(
            'The service is temporarily unavailable. Please try again soon.',
          ),
          findsNothing,
        );
        expect(find.text('Comment 10'), findsOneWidget);
      },
    );

    testWidgets('a failed first load can be retried', (tester) async {
      final app = await openRatings(
        tester,
        first: FakeReply(503, apiError('service_unavailable')),
      );
      expect(
        find.text(
          'The service is temporarily unavailable. Please try again soon.',
        ),
        findsOneWidget,
      );
      app.adapter.setReply(
        'GET',
        path,
        FakeReply(200, page(ratings(1), total: 1)),
      );
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('1 rating(s)'), findsOneWidget);
    });

    testWidgets('pulling down reloads from the first page', (tester) async {
      final app = await openRatings(
        tester,
        // A normal-height screen: the pull distance that starts a refresh depends on the height.
        size: const Size(400, 900),
        first: FakeReply(200, page(ratings(2), total: 2)),
      );
      app.adapter.setReply(
        'GET',
        path,
        FakeReply(200, page([rating(10, comment: 'New one')], total: 3)),
      );
      await tester.drag(find.byType(ListView).first, const Offset(0, 300));
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();
      expect(find.text('New one'), findsOneWidget);
      expect(find.text('3 rating(s)'), findsOneWidget);
    });

    testWidgets(
      'an answer to "Show more" that arrives after a refresh is thrown away',
      (tester) async {
        final gate = Completer<void>();
        final app = await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 30)),
          more: [
            FakeReply(
              200,
              page([rating(5, comment: 'Late one')], total: 30, number: 2),
              const {},
              gate.future,
            ),
          ],
        );
        await tester.tap(showMore);
        await tester.pump();
        await tester.pump(); // "Show more" is in flight
        // The list is refreshed meanwhile (pull down, or a new session).
        app.adapter.setReply(
          'GET',
          path,
          FakeReply(200, page([rating(10, comment: 'Fresh one')], total: 3)),
        );
        ProviderScope.containerOf(tester.element(find.byType(MaterialApp)))
            .invalidate(ratingsControllerProvider);
        await tester.pumpAndSettle();
        expect(find.text('Fresh one'), findsOneWidget);
        gate.complete(); // the old answer arrives now
        await tester.pumpAndSettle();
        expect(find.text('Late one'), findsNothing);
        expect(find.text('3 rating(s)'), findsOneWidget);
        expect(find.byKey(const Key('rating-0')), findsOneWidget);
        expect(
          find.byKey(const Key('rating-1')),
          findsNothing,
        ); // only the fresh list
      },
    );

    testWidgets(
      'after a refresh, "Show more" asks for page 2 again, not page 3',
      (tester) async {
        final gate = Completer<void>();
        final app = await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 30)),
          more: [
            FakeReply(
              200,
              page(ratings(10, from: 10), total: 30, number: 2),
              const {},
              gate.future,
            ),
          ],
        );
        await tester.tap(showMore);
        await tester.pump();
        await tester.pump();
        app.adapter.setReply(
          'GET',
          path,
          FakeReply(200, page(ratings(10), total: 30)),
        );
        ProviderScope.containerOf(tester.element(find.byType(MaterialApp)))
            .invalidate(ratingsControllerProvider);
        await tester.pumpAndSettle();
        gate.complete();
        await tester.pumpAndSettle(); // the stale answer is ignored
        app.adapter.setReply(
          'GET',
          path,
          FakeReply(200, page(ratings(10, from: 10), total: 30, number: 2)),
        );
        await tester.tap(showMore);
        await tester.pumpAndSettle();
        final asked = app.adapter.seen
            .where((r) => r.path == path)
            .map((r) => r.query['page'])
            .toList();
        expect(asked, [
          1,
          2,
          1,
          2,
        ]); // first load, stale "more", refresh, "more" again
        expect(find.text('Comment 10'), findsOneWidget);
      },
    );

    testWidgets(
      'an answer that arrives after the screen was closed does nothing',
      (tester) async {
        final gate = Completer<void>();
        await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 30)),
          more: [
            FakeReply(
              200,
              page(ratings(10, from: 10), total: 30, number: 2),
              const {},
              gate.future,
            ),
          ],
        );
        await tester.tap(showMore);
        await tester.pump();
        await tester.pump();
        ProviderScope.containerOf(tester.element(find.byType(MaterialApp)))
            .read(sessionExpiredProvider.notifier)
            .signal();
        await tester.pumpAndSettle();
        expect(
          find.text('I need to hire'),
          findsOneWidget,
        ); // signed out, back on the welcome screen
        gate.complete();
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets(
      'each rating is read as one item: score, comment and day together',
      (tester) async {
        final handle = tester.ensureSemantics();
        await openRatings(
          tester,
          first: FakeReply(
            200,
            page([
              rating(8, comment: 'Reliable and kind', day: '2026-10-20'),
            ], total: 1),
          ),
        );
        final merged = find.descendant(
          of: find.byKey(const Key('rating-0')),
          matching: find.byType(MergeSemantics),
        );
        final label = tester.getSemantics(merged).label;
        expect(label, contains('8 out of 10'));
        expect(label, contains('Reliable and kind'));
        expect(label, contains(formatDay(DateTime.utc(2026, 10, 20, 10))));
        handle.dispose();
      },
    );

    testWidgets('uses the server words in the lead text', (tester) async {
      await openRatings(
        tester,
        words: churchWords,
        first: FakeReply(200, page([], total: 0)),
      );
      expect(
        find.text(
          'Ratings and comments from searchers. Their names are not shown.',
        ),
        findsOneWidget,
      );
    });
  });

  group('accessibility', () {
    testWidgets(
      'five tabs and the list work at text scale 2.0 on a small phone',
      (tester) async {
        await openRatings(
          tester,
          first: FakeReply(200, page(ratings(10), total: 30)),
          size: const Size(320, 640),
          textScale: 2.0,
        );
        expect(tester.takeException(), isNull);
        await tester.scrollUntilVisible(
          showMore,
          300,
          scrollable: find.byType(Scrollable).first,
        );
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('buttons are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await openRatings(
        tester,
        first: FakeReply(200, page(ratings(10), total: 30)),
      );
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });
}
