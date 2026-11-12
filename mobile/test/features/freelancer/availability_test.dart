import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/date_time_picker.dart';
import 'package:skills_app/core/validation/validators.dart';
import 'package:skills_app/features/freelancer/availability/availability_screen.dart';
import 'package:skills_app/features/freelancer/data/unavailability.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

Map<String, Object?> period(String id, DateTime from, DateTime to) => {
  'id': id,
  'unavailable_from': from.toUtc().toIso8601String(),
  'unavailable_to': to.toUtc().toIso8601String(),
};

final nov5 = DateTime.utc(2026, 11, 5, 9);
final nov8 = DateTime.utc(2026, 11, 8, 18, 30);
final dec1 = DateTime.utc(2026, 12, 1, 8);
final dec3 = DateTime.utc(2026, 12, 3, 20);

Future<TestApp> openAvailability(
  WidgetTester tester, {
  List<Map<String, Object?>>? periods,
  FakeReply? reply,
  FakePicker? picker,
  Map<String, String> words = defaultWords,
  Size size = const Size(400, 900),
  double textScale = 1.0,
}) async {
  final app = await pumpApp(
    tester,
    words: words,
    size: size,
    textScale: textScale,
    overrides: [
      if (picker != null) dateTimePickerProvider.overrideWithValue(picker.call),
    ],
    arrange: (adapter, store) {
      signedInAs(adapter, store, 'freelancer');
      adapter.reply(
        'GET',
        '/freelancers/me/unavailability',
        reply ?? FakeReply(200, periods ?? <Object?>[]),
      );
    },
  );
  await tapTab(tester, 'Availability');
  return app;
}

Future<void> tapText(WidgetTester tester, String text) async {
  await tester.tap(find.text(text).last);
  await tester.pumpAndSettle();
}

void main() {
  group('rules', () {
    test('both ends are needed and the end must be after the start', () {
      expect(validatePeriod(from: null, to: null), {
        'from': 'validation.periodRequired',
        'to': 'validation.periodRequired',
      });
      expect(validatePeriod(from: nov5, to: null).keys, ['to']);
      expect(validatePeriod(from: nov5, to: nov8), isEmpty);
      expect(
        validatePeriod(from: nov8, to: nov5)['to'],
        'validation.periodOrder',
      );
      expect(
        validatePeriod(from: nov5, to: nov5)['to'],
        'validation.periodOrder',
      ); // equal is not after
    });

    test('a period is read in UTC and sent as UTC', () {
      final read = Unavailability.fromJson({
        'id': 'p1',
        'unavailable_from': '2026-11-05T13:00:00+04:00',
        'unavailable_to': '2026-11-05T20:00:00Z',
      });
      expect(read.from, DateTime.utc(2026, 11, 5, 9));
      expect(read.to.isUtc, isTrue);
      expect(
        periodBody(
          DateTime(2026, 11, 5, 9),
          DateTime(2026, 11, 6, 9),
        ).values.every((v) => (v! as String).endsWith('Z')),
        isTrue,
      );
    });
  });

  group('list', () {
    testWidgets('has its own tab and a dashboard shortcut', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'freelancer'));
      expect(
        find.descendant(
          of: find.byType(NavigationBar),
          matching: find.text('Availability'),
        ),
        findsOneWidget,
      );
      expect(find.text('Availability'), findsNWidgets(2)); // tab + shortcut
    });

    testWidgets('is not offered to other roles', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'workhost'));
      expect(find.text('Availability'), findsNothing);
    });

    testWidgets('says so when there are no periods, with the server words', (
      tester,
    ) async {
      await openAvailability(tester, words: churchWords);
      expect(
        find.text(
          'You have no unavailable periods. Searchers see you as available.',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          'Add the periods when you cannot work. Searchers see upcoming periods.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('shows the periods oldest first, in local time', (
      tester,
    ) async {
      await openAvailability(
        tester,
        periods: [period('p2', dec1, dec3), period('p1', nov5, nov8)],
      );
      final first = find.text(
        'From ${formatPeriodTime(nov5)} until ${formatPeriodTime(nov8)}',
      );
      final second = find.text(
        'From ${formatPeriodTime(dec1)} until ${formatPeriodTime(dec3)}',
      );
      expect(first, findsOneWidget);
      expect(second, findsOneWidget);
      expect(
        tester.getTopLeft(first).dy,
        lessThan(tester.getTopLeft(second).dy),
      );
    });

    testWidgets('a failed load can be retried', (tester) async {
      final app = await openAvailability(
        tester,
        reply: FakeReply(503, apiError('service_unavailable')),
      );
      expect(
        find.text(
          'The service is temporarily unavailable. Please try again soon.',
        ),
        findsOneWidget,
      );
      app.adapter.setReply(
        'GET',
        '/freelancers/me/unavailability',
        FakeReply(200, [period('p1', nov5, nov8)]),
      );
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('period-p1')), findsOneWidget);
    });
  });

  group('add', () {
    testWidgets('asks for both ends before sending anything', (tester) async {
      final app = await openAvailability(tester, picker: FakePicker([]));
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      expect(find.text('Add a period'), findsWidgets);
      await tester.tap(find.byKey(const Key('period-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Choose a date and time.'), findsNWidgets(2));
      expect(app.adapter.count('POST', '/freelancers/me/unavailability'), 0);
    });

    testWidgets('sends UTC times, closes, confirms and reloads the list', (
      tester,
    ) async {
      final picker = FakePicker([nov5, nov8]);
      final app = await openAvailability(tester, picker: picker);
      app.adapter.reply(
        'POST',
        '/freelancers/me/unavailability',
        FakeReply(201, period('p1', nov5, nov8)),
      );
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-from')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-to')));
      await tester.pumpAndSettle();
      expect(find.text(formatPeriodTime(nov5)), findsOneWidget);
      expect(find.text(formatPeriodTime(nov8)), findsOneWidget);
      app.adapter.setReply(
        'GET',
        '/freelancers/me/unavailability',
        FakeReply(200, [period('p1', nov5, nov8)]),
      );
      await tester.tap(find.byKey(const Key('period-submit')));
      await tester.pumpAndSettle();
      final body =
          app.adapter.seen
                  .firstWhere(
                    (r) =>
                        r.method == 'POST' &&
                        r.path == '/freelancers/me/unavailability',
                  )
                  .body!
              as Map;
      expect(body, {
        'unavailable_from': nov5.toIso8601String(),
        'unavailable_to': nov8.toIso8601String(),
      });
      expect(
        find.byKey(const Key('period-submit')),
        findsNothing,
      ); // the sheet closed
      expect(find.text('Saved.'), findsOneWidget);
      expect(find.byKey(const Key('period-p1')), findsOneWidget);
      expect(app.adapter.count('GET', '/freelancers/me/unavailability'), 2);
    });

    testWidgets('an end before the start is refused on the phone', (
      tester,
    ) async {
      final app = await openAvailability(
        tester,
        picker: FakePicker([nov8, nov5]),
      );
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-from')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-to')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('period-submit')));
      await tester.pumpAndSettle();
      expect(find.text('The end must be after the start.'), findsOneWidget);
      expect(app.adapter.count('POST', '/freelancers/me/unavailability'), 0);
    });

    testWidgets(
      'an overlapping period shows the message and keeps the form open',
      (tester) async {
        final app = await openAvailability(
          tester,
          picker: FakePicker([nov5, nov8]),
        );
        app.adapter.reply(
          'POST',
          '/freelancers/me/unavailability',
          FakeReply(409, apiError('unavailability_overlaps')),
        );
        await tester.tap(find.byKey(const Key('add-period')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('pick-from')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('pick-to')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('period-submit')));
        await tester.pumpAndSettle();
        expect(
          find.text('This period overlaps one you already have.'),
          findsOneWidget,
        );
        expect(
          find.text(formatPeriodTime(nov5)),
          findsOneWidget,
        ); // what was chosen is kept
        expect(find.byKey(const Key('period-submit')), findsOneWidget);
      },
    );

    testWidgets('cancelling the picker changes nothing', (tester) async {
      await openAvailability(tester, picker: FakePicker([null]));
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-from')));
      await tester.pumpAndSettle();
      expect(find.text('Choose date and time'), findsNWidgets(2));
    });

    testWidgets('the real pickers open and return a moment', (tester) async {
      await openAvailability(tester);
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('pick-from')));
      await tester.pumpAndSettle();
      expect(find.byType(DatePickerDialog), findsOneWidget);
      await tapText(tester, 'OK');
      expect(find.byType(TimePickerDialog), findsOneWidget);
      await tapText(tester, 'OK');
      expect(
        find.text('Choose date and time'),
        findsOneWidget,
      ); // only "Until" is still empty
    });
  });

  group('edit and delete', () {
    testWidgets(
      'edit starts from the saved times and sends a change to that period',
      (tester) async {
        final picker = FakePicker([dec3]);
        final app = await openAvailability(
          tester,
          periods: [period('p1', nov5, nov8)],
          picker: picker,
        );
        app.adapter.reply(
          'PUT',
          '/freelancers/me/unavailability/p1',
          FakeReply(200, period('p1', nov5, dec3)),
        );
        await tester.tap(find.byKey(const Key('edit-p1')));
        await tester.pumpAndSettle();
        expect(find.text('Change period'), findsOneWidget);
        expect(find.text(formatPeriodTime(nov5)), findsOneWidget);
        expect(find.text(formatPeriodTime(nov8)), findsOneWidget);
        await tester.tap(find.byKey(const Key('pick-to')));
        await tester.pumpAndSettle();
        expect(
          picker.asked.single!.toUtc(),
          nov8,
        ); // the picker starts from the saved end
        await tester.tap(find.byKey(const Key('period-submit')));
        await tester.pumpAndSettle();
        final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
        expect(put.path, '/freelancers/me/unavailability/p1');
        expect(put.body, {
          'unavailable_from': nov5.toIso8601String(),
          'unavailable_to': dec3.toIso8601String(),
        });
      },
    );

    testWidgets('delete asks first; cancel sends nothing', (tester) async {
      final app = await openAvailability(
        tester,
        periods: [period('p1', nov5, nov8)],
      );
      await tester.tap(find.byKey(const Key('delete-p1')));
      await tester.pumpAndSettle();
      expect(find.text('Delete this period?'), findsOneWidget);
      await tapText(tester, 'Cancel');
      expect(app.adapter.seen.where((r) => r.method == 'DELETE'), isEmpty);
      expect(find.byKey(const Key('period-p1')), findsOneWidget);
    });

    testWidgets('confirming deletes the period and reloads the list', (
      tester,
    ) async {
      final app = await openAvailability(
        tester,
        periods: [period('p1', nov5, nov8)],
      );
      app.adapter.reply(
        'DELETE',
        '/freelancers/me/unavailability/p1',
        FakeReply(204),
      );
      app.adapter.setReply(
        'GET',
        '/freelancers/me/unavailability',
        FakeReply(200, <Object?>[]),
      );
      await tester.tap(find.byKey(const Key('delete-p1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-delete')));
      await tester.pumpAndSettle();
      expect(
        app.adapter.count('DELETE', '/freelancers/me/unavailability/p1'),
        1,
      );
      expect(find.byKey(const Key('period-p1')), findsNothing);
      expect(
        find.text(
          'You have no unavailable periods. Freelancers see you as available.'
              .replaceAll('Freelancers', 'Work hosts'),
        ),
        findsOneWidget,
      );
    });

    testWidgets(
      'a period already deleted elsewhere shows the message and leaves the list',
      (tester) async {
        final app = await openAvailability(
          tester,
          periods: [period('p1', nov5, nov8)],
        );
        app.adapter.reply(
          'DELETE',
          '/freelancers/me/unavailability/p1',
          FakeReply(404, apiError('not_found')),
        );
        app.adapter.setReply(
          'GET',
          '/freelancers/me/unavailability',
          FakeReply(200, <Object?>[]),
        );
        await tester.tap(find.byKey(const Key('delete-p1')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('confirm-delete')));
        await tester.pumpAndSettle();
        expect(
          find.text('That item no longer exists. Go back and try again.'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('period-p1')), findsNothing);
      },
    );
  });

  group('accessibility', () {
    testWidgets('works at text scale 2.0 on a small phone', (tester) async {
      await openAvailability(
        tester,
        periods: [period('p1', nov5, nov8), period('p2', dec1, dec3)],
        size: const Size(320, 640),
        textScale: 2.0,
      );
      expect(tester.takeException(), isNull);
      await tester.tap(find.byKey(const Key('add-period')));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('period-submit')), findsOneWidget);
    });

    testWidgets('buttons are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await openAvailability(tester, periods: [period('p1', nov5, nov8)]);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });
}
