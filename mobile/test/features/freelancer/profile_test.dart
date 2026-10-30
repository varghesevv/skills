import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

Map<String, Object?> profileJson({
  String? name = 'Pat Example',
  Object? rate = 45.5,
  String? currency = 'AED',
  bool negotiable = true,
  bool whatsapp = true,
  String? nationality = 'Examplean',
  String? language = 'English',
}) => {
  'id': 'f1',
  'full_name': name,
  'email': 'person@example.test',
  'mobile_number': '+971501234567',
  'whatsapp_availability': whatsapp,
  'nationality': nationality,
  'primary_language': language,
  'rate_per_hour': rate,
  'rate_currency': currency,
  'is_rate_negotiable': negotiable,
  'labels': <Object?>[],
  'created_at': '2026-10-01T10:00:00Z',
};

Future<TestApp> openProfile(
  WidgetTester tester, {
  Map<String, Object?>? profile,
  FakeReply? reply,
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
      adapter.reply(
        'GET',
        '/freelancers/me',
        reply ?? FakeReply(200, profile ?? profileJson()),
      );
    },
  );
  await tapTab(tester, 'Profile');
  return app;
}

String fieldText(WidgetTester tester, String label) => tester
    .widget<TextField>(find.widgetWithText(TextField, label))
    .controller!
    .text;

void main() {
  group('navigation', () {
    testWidgets('a freelancer has Home, Profile and Settings', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'freelancer'));
      Finder tab(String label) => find.descendant(
        of: find.byType(NavigationBar),
        matching: find.text(label),
      );
      expect(tab('Home'), findsOneWidget);
      expect(tab('Profile'), findsOneWidget);
      expect(tab('Settings'), findsOneWidget);
    });

    testWidgets('a work host has no Profile tab yet', (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'workhost'));
      expect(find.text('Profile'), findsNothing);
      expect(find.text('Settings'), findsOneWidget);
    });

    testWidgets("another role's pages are never shown", (tester) async {
      await pumpApp(tester, arrange: (a, s) => signedInAs(a, s, 'workhost'));
      final router = ProviderScope.containerOf(
        tester.element(find.byType(MaterialApp)),
      ).read(routerProvider);
      router.go('/freelancer/profile');
      await tester.pumpAndSettle();
      expect(find.text('Your profile'), findsNothing);
      expect(find.text('Welcome, Pat Example'), findsOneWidget);
    });
  });

  group('profile screen', () {
    testWidgets('shows the saved values', (tester) async {
      await openProfile(tester);
      expect(fieldText(tester, 'Full name'), 'Pat Example');
      expect(fieldText(tester, 'Mobile number'), '+971501234567');
      expect(fieldText(tester, 'Nationality'), 'Examplean');
      expect(fieldText(tester, 'Primary language'), 'English');
      expect(fieldText(tester, 'Rate per hour'), '45.5');
      expect(fieldText(tester, 'Currency'), 'AED');
    });

    testWidgets(
      'a whole-number rate is shown without decimals and no rate is empty',
      (tester) async {
        await openProfile(tester, profile: profileJson(rate: 45.0));
        expect(fieldText(tester, 'Rate per hour'), '45');
      },
    );

    testWidgets('a profile without a rate shows empty rate fields', (
      tester,
    ) async {
      await openProfile(
        tester,
        profile: profileJson(
          rate: null,
          currency: null,
          nationality: null,
          language: null,
        ),
      );
      expect(fieldText(tester, 'Rate per hour'), isEmpty);
      expect(fieldText(tester, 'Currency'), isEmpty);
      expect(fieldText(tester, 'Nationality'), isEmpty);
    });

    testWidgets('uses the server words in the lead text', (tester) async {
      await openProfile(tester, words: churchWords);
      expect(
        find.text(
          'Providers see your name, rate and details when they find you.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('a failed load shows the message and loads again on retry', (
      tester,
    ) async {
      final app = await openProfile(
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
        '/freelancers/me',
        FakeReply(200, profileJson()),
      );
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(fieldText(tester, 'Full name'), 'Pat Example');
    });

    testWidgets('checks the fields before saving', (tester) async {
      final app = await openProfile(tester);
      await typeInto(tester, 'Full name', 'P');
      await typeInto(tester, 'Mobile number', 'call me');
      await typeInto(tester, 'Rate per hour', '45.555');
      await typeInto(tester, 'Currency', 'DIRHAM'.substring(0, 2));
      await tapKey(tester, 'profile-save');
      expect(
        find.text('Enter your name (2 to 200 characters).'),
        findsOneWidget,
      );
      expect(
        find.text('Enter 7 to 15 digits, optionally starting with +.'),
        findsOneWidget,
      );
      expect(find.text('Enter an amount such as 45 or 45.50.'), findsOneWidget);
      expect(
        find.text('Use a 3-letter currency code such as AED.'),
        findsOneWidget,
      );
      expect(app.adapter.count('PUT', '/freelancers/me'), 0);
    });

    testWidgets('a rate needs a currency and a currency needs a rate', (
      tester,
    ) async {
      await openProfile(
        tester,
        profile: profileJson(rate: null, currency: null),
      );
      await typeInto(tester, 'Rate per hour', '30');
      await tapKey(tester, 'profile-save');
      expect(
        find.text(
          'Give both the hourly rate and the currency, or leave both empty.',
        ),
        findsOneWidget,
      );
      await typeInto(tester, 'Rate per hour', '');
      await typeInto(tester, 'Currency', 'usd');
      await tapKey(tester, 'profile-save');
      expect(
        find.text(
          'Give both the hourly rate and the currency, or leave both empty.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('saves a clean body and shows the confirmation', (
      tester,
    ) async {
      final app = await openProfile(tester);
      await typeInto(tester, 'Full name', '  Pat Changed ');
      await typeInto(tester, 'Mobile number', '+971 50-111 2222');
      await typeInto(tester, 'Nationality', '');
      await typeInto(tester, 'Rate per hour', '60');
      await typeInto(tester, 'Currency', 'usd');
      app.adapter.reply(
        'PUT',
        '/freelancers/me',
        FakeReply(
          200,
          profileJson(
            name: 'Pat Changed',
            rate: 60.0,
            currency: 'USD',
            nationality: null,
          ),
        ),
      );
      await tapKey(tester, 'profile-save');
      final body =
          app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
      expect(body, {
        'full_name': 'Pat Changed',
        'mobile_number': '+971501112222',
        'whatsapp_availability': true,
        'nationality': null,
        'primary_language': 'English',
        'rate_per_hour': 60.0,
        'rate_currency': 'USD',
        'is_rate_negotiable': true,
      });
      expect(find.text('Saved.'), findsOneWidget);
      expect(fieldText(tester, 'Rate per hour'), '60');
      expect(fieldText(tester, 'Currency'), 'USD');
    });

    testWidgets('clearing the rate and the currency sends nulls', (
      tester,
    ) async {
      final app = await openProfile(tester);
      await typeInto(tester, 'Rate per hour', '');
      await typeInto(tester, 'Currency', '');
      app.adapter.reply(
        'PUT',
        '/freelancers/me',
        FakeReply(200, profileJson(rate: null, currency: null)),
      );
      await tapKey(tester, 'profile-save');
      final body =
          app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
      expect(body['rate_per_hour'], isNull);
      expect(body['rate_currency'], isNull);
    });

    testWidgets('the checkboxes are saved', (tester) async {
      final app = await openProfile(tester);
      for (final label in [
        'I am available on WhatsApp',
        'The rate is negotiable',
      ]) {
        final tile = find.widgetWithText(CheckboxListTile, label);
        await tester.scrollUntilVisible(
          tile,
          100,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        await tester.tap(tile, warnIfMissed: false);
        await tester.pumpAndSettle();
      }
      app.adapter.reply(
        'PUT',
        '/freelancers/me',
        FakeReply(200, profileJson(whatsapp: false, negotiable: false)),
      );
      await tapKey(tester, 'profile-save');
      final body =
          app.adapter.seen.firstWhere((r) => r.method == 'PUT').body! as Map;
      expect(body['whatsapp_availability'], false);
      expect(body['is_rate_negotiable'], false);
    });

    testWidgets(
      'server field errors appear at the field and the confirmation is not shown',
      (tester) async {
        final app = await openProfile(tester);
        app.adapter.reply(
          'PUT',
          '/freelancers/me',
          FakeReply(422, {
            'error': {
              'code': 'validation_error',
              'message': 'm',
              'details': {
                'fields': [
                  {
                    'field': 'mobile_number',
                    'message': 'Not a valid number for this country.',
                  },
                ],
              },
            },
          }),
        );
        await tapKey(tester, 'profile-save');
        expect(
          find.text('Not a valid number for this country.'),
          findsOneWidget,
        );
        expect(
          find.text('Please correct the highlighted fields.'),
          findsOneWidget,
        );
        expect(find.text('Saved.'), findsNothing);
      },
    );

    testWidgets('editing after a save hides the confirmation', (tester) async {
      final app = await openProfile(tester);
      app.adapter.reply(
        'PUT',
        '/freelancers/me',
        FakeReply(200, profileJson()),
      );
      await tapKey(tester, 'profile-save');
      expect(find.text('Saved.'), findsOneWidget);
      await typeInto(tester, 'Full name', 'Someone Else');
      await tester.pump();
      expect(find.text('Saved.'), findsNothing);
    });

    testWidgets('suggests currencies while typing', (tester) async {
      await openProfile(
        tester,
        profile: profileJson(rate: null, currency: null),
      );
      await tester.ensureVisible(find.widgetWithText(TextField, 'Currency'));
      await tester.enterText(find.widgetWithText(TextField, 'Currency'), 'u');
      await tester.pumpAndSettle();
      expect(find.text('USD'), findsOneWidget);
      await tester.tap(find.text('USD'));
      await tester.pumpAndSettle();
      expect(fieldText(tester, 'Currency'), 'USD');
    });
  });

  group('accessibility', () {
    testWidgets('works at text scale 2.0 on a small phone', (tester) async {
      await openProfile(tester, size: const Size(320, 640), textScale: 2.0);
      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.byKey(const Key('profile-save')),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('tap targets are large enough and labelled', (tester) async {
      final handle = tester.ensureSemantics();
      await openProfile(tester);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });
  });
}
