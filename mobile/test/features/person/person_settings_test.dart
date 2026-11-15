import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/core/providers.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Future<TestApp> _open(
  WidgetTester tester, {
  String version = '1.0.0',
  String privacy = '',
  Future<bool> Function(Uri)? launcher,
  String status = 'searcher',
}) => pumpApp(
  tester,
  appVersion: version,
  overrides: [
    privacyUrlProvider.overrideWithValue(privacy),
    if (launcher != null) webLauncherProvider.overrideWithValue(launcher),
  ],
  arrange: (adapter, store) {
    signedInAsPerson(
      adapter,
      store,
      personJson(status: status, requested: null),
    );
    adapter.reply('GET', '/me/notifications', FakeReply(200, _noNotes));
  },
);

Future<void> _goToSettings(WidgetTester tester) => tapKey(tester, 'settings');

void main() {
  test(
    'settings are for everyone admitted, not for applicants or the revoked',
    () {
      PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
      for (final s in ['searcher', 'provider', 'verifier', 'admin', 'owner']) {
        expect(personMayVisit(of(s), '/member/settings'), isTrue, reason: s);
      }
      for (final s in ['pending', 'revoked']) {
        expect(personMayVisit(of(s), '/member/settings'), isFalse, reason: s);
      }
    },
  );

  testWidgets('shows the version and an update hint when a newer one exists', (
    tester,
  ) async {
    await _open(tester); // the fake server's latest version is 9.9.9
    await _goToSettings(tester);
    expect(find.text('1.0.0'), findsOneWidget);
    expect(find.byKey(const Key('update-hint')), findsOneWidget);
  });

  testWidgets('no hint when this is the latest version', (tester) async {
    await _open(tester, version: '9.9.9');
    await _goToSettings(tester);
    expect(find.byKey(const Key('update-hint')), findsNothing);
  });

  testWidgets('no hint and no failure when the version is unknown (dev)', (
    tester,
  ) async {
    await _open(tester, version: '');
    await _goToSettings(tester);
    expect(find.text('dev'), findsOneWidget);
    expect(find.byKey(const Key('update-hint')), findsNothing);
  });

  testWidgets('the privacy row only shows when the build has an address', (
    tester,
  ) async {
    await _open(tester);
    await _goToSettings(tester);
    expect(find.byKey(const Key('privacy')), findsNothing);
  });

  testWidgets('the privacy row opens the address', (tester) async {
    Uri? opened;
    await _open(
      tester,
      privacy: 'https://example.test/privacy',
      launcher: (u) async {
        opened = u;
        return true;
      },
    );
    await _goToSettings(tester);
    await tapKey(tester, 'privacy');
    expect(opened.toString(), 'https://example.test/privacy');
    expect(find.textContaining('could not be opened'), findsNothing);
  });

  for (final fails in ['false', 'throws']) {
    testWidgets('a browser that $fails is explained', (tester) async {
      await _open(
        tester,
        privacy: 'https://example.test/privacy',
        launcher: (u) async {
          if (fails == 'throws') throw Exception('no browser');
          return false;
        },
      );
      await _goToSettings(tester);
      await tapKey(tester, 'privacy');
      expect(find.textContaining('could not be opened'), findsOneWidget);
    });
  }

  testWidgets('log out returns to the welcome screen', (tester) async {
    final app = await _open(tester);
    await _goToSettings(tester);
    await tapKey(tester, 'settings-log-out');
    expect(app.adapter.count('POST', '/auth/logout'), 1);
    expect(find.byKey(const Key('settings-log-out')), findsNothing);
  });

  testWidgets('fits at double text size', (tester) async {
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await _open(tester, privacy: 'https://example.test/privacy');
    await _goToSettings(tester);
    expect(tester.takeException(), isNull);
  });
}
