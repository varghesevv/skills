import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/features/freelancer/data/label.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';
import 'profile_test.dart' show profileJson;

Map<String, Object?> label(String id, String name, String type) => {
  'id': id,
  'label_name': name,
  'label_type': type,
  'is_active': true,
};

// Deliberately not in display order, to prove the screen sorts levels.
final catalog = [
  label('s1', 'Carpentry', 'skill'),
  label('s2', 'Painting', 'skill'),
  label('s3', 'Plumbing', 'skill'),
  label('l1', 'Arabic', 'language'),
  label('l2', 'English', 'language'),
  label('n1', 'Native', 'nativity'),
  label('v3', '80%', 'skill_level'),
  label('v1', 'basic', 'skill_level'),
  label('v2', '50%', 'skill_level'),
  label('v4', '100%', 'skill_level'),
];

Map<String, Object?> withLabels(List<Map<String, Object?>> chosen) => {
  ...profileJson(),
  'labels': chosen,
};

Map<String, Object?> chosen(
  Map<String, Object?> label, [
  Map<String, Object?>? level,
]) => {'label': label, 'level': level};

Future<TestApp> openLabels(
  WidgetTester tester, {
  List<Map<String, Object?>>? labels,
  List<Map<String, Object?>>? catalogJson,
  FakeReply? catalogReply,
  Map<String, String> words = defaultWords,
  Size size = const Size(400, 900),
  double textScale = 1.0,
}) async {
  final app = await pumpApp(
    tester,
    words: words,
    size: size,
    textScale: textScale,
    arrange: (adapter, store) {
      signedInAs(adapter, store, 'freelancer');
      adapter
        ..reply(
          'GET',
          '/freelancers/me',
          FakeReply(
            200,
            withLabels(
              labels ??
                  [
                    chosen(
                      label('s3', 'Plumbing', 'skill'),
                      label('v3', '80%', 'skill_level'),
                    ),
                    chosen(label('l2', 'English', 'language')),
                    // An admin switched this label off: it is no longer in the catalogue.
                    chosen(label('x9', 'Welding', 'skill')),
                  ],
            ),
          ),
        )
        ..reply(
          'GET',
          '/labels',
          catalogReply ?? FakeReply(200, catalogJson ?? catalog),
        );
    },
  );
  final shortcut = find.text('Skills and labels');
  if (shortcut.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      shortcut,
      200,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(shortcut);
  await tester.pumpAndSettle();
  await tester.tap(shortcut);
  await tester.pumpAndSettle();
  return app;
}

Future<void> check(WidgetTester tester, String name) async {
  final tile = find.widgetWithText(CheckboxListTile, name);
  await tester.scrollUntilVisible(
    tile,
    100,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  await tester.tap(tile, warnIfMissed: false);
  await tester.pumpAndSettle();
}

bool isChecked(WidgetTester tester, String name) => tester
    .widget<CheckboxListTile>(find.widgetWithText(CheckboxListTile, name))
    .value!;

void main() {
  group('sortLevels', () {
    Label level(String name) =>
        Label(id: name, name: name, type: 'skill_level', isActive: true);
    List<String> order(List<String> names) =>
        sortLevels(names.map(level).toList()).map((l) => l.name).toList();

    test('words first, then by number (not as text)', () {
      expect(order(['80%', 'basic', '50%', '100%']), [
        'basic',
        '50%',
        '80%',
        '100%',
      ]);
    });

    test('words are sorted among themselves, ignoring case', () {
      expect(order(['Expert', 'basic', 'Advanced']), [
        'Advanced',
        'basic',
        'Expert',
      ]);
    });

    test('the same number keeps a stable, alphabetical order', () {
      expect(order(['50% b', '50% a']), ['50% a', '50% b']);
    });
  });

  group('labels screen', () {
    testWidgets('is reached from the dashboard and shows the saved choice', (
      tester,
    ) async {
      await openLabels(tester);
      expect(
        find.text(
          'Choose what work hosts can search for. Give each skill a level if you like. Saving replaces your whole selection.',
        ),
        findsOneWidget,
      );
      expect(find.text('Skills (1 selected)'), findsOneWidget);
      expect(find.text('Languages (1 selected)'), findsOneWidget);
      expect(isChecked(tester, 'Plumbing'), isTrue);
      expect(isChecked(tester, 'Carpentry'), isFalse);
      expect(isChecked(tester, 'English'), isTrue);
      expect(find.text('Welding'), findsNothing); // switched off by an admin
      await tester.scrollUntilVisible(
        find.text('Nativity (0 selected)'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Nativity (0 selected)'), findsOneWidget);
    });

    testWidgets('a kind without labels says so', (tester) async {
      await openLabels(tester);
      await tester.scrollUntilVisible(
        find.text('Timings (0 selected)'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.text('No labels of this kind are available yet.'),
        findsOneWidget,
      );
    });

    testWidgets(
      'only a chosen skill has a level, and the saved level is shown',
      (tester) async {
        await openLabels(tester);
        expect(find.byKey(const Key('level-s3')), findsOneWidget);
        expect(find.byKey(const Key('level-s1')), findsNothing);
        expect(find.text('80%'), findsWidgets);
        await check(tester, 'Carpentry');
        expect(find.byKey(const Key('level-s1')), findsOneWidget);
        await check(tester, 'Carpentry');
        expect(find.byKey(const Key('level-s1')), findsNothing);
      },
    );

    testWidgets(
      'levels are offered with "No level" first, words, then numbers',
      (tester) async {
        await openLabels(tester);
        await tester.tap(find.byKey(const Key('level-s3')));
        await tester.pumpAndSettle();
        final shown = tester.widgetList<Text>(
          find.descendant(
            of: find.byType(Scrollable).last,
            matching: find.byType(Text),
          ),
        );
        final names = shown
            .map((t) => t.data)
            .whereType<String>()
            .where(
              (t) => ['No level', 'basic', '50%', '80%', '100%'].contains(t),
            )
            .toList();
        // The open menu lists them in order (the closed field repeats the chosen "80%").
        expect(
          names
              .where(
                (n) =>
                    n != '80%' ||
                    names.indexOf(n) == names.lastIndexOf(n) ||
                    true,
              )
              .toList(),
          containsAllInOrder(['No level', 'basic', '50%', '80%', '100%']),
        );
      },
    );

    testWidgets(
      'saves the whole selection in catalogue order, with levels only on skills',
      (tester) async {
        final app = await openLabels(tester);
        await check(tester, 'Carpentry');
        await check(tester, 'Arabic');
        await check(tester, 'English'); // remove English
        await check(tester, 'Native');
        app.adapter.reply(
          'PUT',
          '/freelancers/me/labels',
          FakeReply(200, <Object?>[]),
        );
        await tapKey(tester, 'labels-save');
        final body =
            app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
        expect(body, {
          'labels': [
            {'label_id': 's1', 'level_label_id': null},
            {'label_id': 's3', 'level_label_id': 'v3'},
            {'label_id': 'l1', 'level_label_id': null},
            {'label_id': 'n1', 'level_label_id': null},
          ],
        });
        expect(find.text('Saved.'), findsOneWidget);
      },
    );

    testWidgets('a level can be changed and cleared', (tester) async {
      final app = await openLabels(tester);
      await tester.tap(find.byKey(const Key('level-s3')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('No level').last);
      await tester.pumpAndSettle();
      app.adapter.reply(
        'PUT',
        '/freelancers/me/labels',
        FakeReply(200, <Object?>[]),
      );
      await tapKey(tester, 'labels-save');
      final body =
          app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
      expect((body['labels'] as List).first, {
        'label_id': 's3',
        'level_label_id': null,
      });
    });

    testWidgets(
      'a level the server attached to a non-skill label is not sent back',
      (tester) async {
        final app = await openLabels(
          tester,
          labels: [
            chosen(
              label('s3', 'Plumbing', 'skill'),
              label('v3', '80%', 'skill_level'),
            ),
            // Levels belong to skills; this one could be neither seen nor cleared on this screen.
            chosen(
              label('l2', 'English', 'language'),
              label('v1', 'basic', 'skill_level'),
            ),
          ],
        );
        app.adapter.reply(
          'PUT',
          '/freelancers/me/labels',
          FakeReply(200, <Object?>[]),
        );
        await tapKey(tester, 'labels-save');
        final body =
            app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
        expect(body['labels'], [
          {'label_id': 's3', 'level_label_id': 'v3'},
          {'label_id': 'l2', 'level_label_id': null},
        ]);
      },
    );

    testWidgets('choosing nothing at all is saved as an empty set', (
      tester,
    ) async {
      final app = await openLabels(tester);
      await check(tester, 'Plumbing');
      await check(tester, 'English');
      app.adapter.reply(
        'PUT',
        '/freelancers/me/labels',
        FakeReply(200, <Object?>[]),
      );
      await tapKey(tester, 'labels-save');
      expect(
        (app.adapter.seen.firstWhere((r) => r.method == 'PUT').body!
            as Map)['labels'],
        isEmpty,
      );
    });

    testWidgets('the confirmation goes away when the choice changes', (
      tester,
    ) async {
      final app = await openLabels(tester);
      app.adapter.reply(
        'PUT',
        '/freelancers/me/labels',
        FakeReply(200, <Object?>[]),
      );
      await tapKey(tester, 'labels-save');
      expect(find.text('Saved.'), findsOneWidget);
      await check(tester, 'Painting');
      expect(find.text('Saved.'), findsNothing);
    });

    testWidgets(
      'a label that is no longer available shows the message, not the confirmation',
      (tester) async {
        final app = await openLabels(tester);
        app.adapter.reply(
          'PUT',
          '/freelancers/me/labels',
          FakeReply(422, apiError('unknown_label')),
        );
        await tapKey(tester, 'labels-save');
        expect(
          find.text(
            'One of the selected labels is no longer available. Go back and try again.',
          ),
          findsOneWidget,
        );
        expect(find.text('Saved.'), findsNothing);
      },
    );

    testWidgets('a failed catalogue load can be retried', (tester) async {
      final app = await openLabels(
        tester,
        catalogReply: FakeReply(503, apiError('service_unavailable')),
      );
      expect(
        find.text(
          'The service is temporarily unavailable. Please try again soon.',
        ),
        findsOneWidget,
      );
      app.adapter.setReply('GET', '/labels', FakeReply(200, catalog));
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Skills (1 selected)'), findsOneWidget);
    });

    testWidgets('the lead text uses the server words', (tester) async {
      await openLabels(tester, words: churchWords);
      expect(
        find.textContaining('Choose what providers can search for.'),
        findsOneWidget,
      );
    });

    testWidgets('works at text scale 2.0 on a small phone', (tester) async {
      await openLabels(tester, size: const Size(320, 640), textScale: 2.0);
      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.byKey(const Key('labels-save')),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('tap targets are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await openLabels(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });

  group('navigation to the labels screen', () {
    testWidgets('the Profile screen links to it, and Back returns', (
      tester,
    ) async {
      await pumpApp(
        tester,
        size: const Size(400, 900),
        arrange: (adapter, store) {
          signedInAs(adapter, store, 'freelancer');
          adapter
            ..reply('GET', '/freelancers/me', FakeReply(200, withLabels([])))
            ..reply('GET', '/labels', FakeReply(200, catalog));
        },
      );
      await tapTab(tester, 'Profile');
      await tester.tap(find.byKey(const Key('open-labels')));
      await tester.pumpAndSettle();
      expect(find.text('Skills (0 selected)'), findsOneWidget);
      expect(
        find.byType(NavigationBar),
        findsOneWidget,
      ); // the bottom bar stays
    });

    testWidgets('a work host has no such shortcut', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'workhost'));
      expect(find.text('Skills and labels'), findsNothing);
      expect(find.text('Where to go next'), findsNothing);
    });
  });
}
