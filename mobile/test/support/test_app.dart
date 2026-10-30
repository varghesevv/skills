import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/app.dart';

import 'memory_token_store.dart';

import 'package:skills_app/core/providers.dart';

import 'fake_api.dart';

/// The words the server returns for each profile (test data; the app has no copy of them).
const defaultWords = {
  'organisation': 'Organisation',
  'organisations': 'Organisations',
  'organisation_path': 'organisation',
  'organisations_path': 'organisations',
  'workhost': 'Work host',
  'workhosts': 'Work hosts',
  'workhost_path': 'workhost',
  'freelancer': 'Freelancer',
  'freelancers': 'Freelancers',
  'freelancer_path': 'freelancer',
  'freelancers_path': 'freelancers',
  'badge_organisation': 'Organisation',
  'badge_workhost': 'Work host',
  'badge_freelancer': 'Freelancer',
}; // fmt: skip
const churchWords = {
  'organisation': 'Church',
  'organisations': 'Churches',
  'organisation_path': 'church',
  'organisations_path': 'churches',
  'workhost': 'Provider',
  'workhosts': 'Providers',
  'workhost_path': 'provider',
  'freelancer': 'Searcher',
  'freelancers': 'Searchers',
  'freelancer_path': 'searcher',
  'freelancers_path': 'searchers',
  'badge_organisation': 'Church',
  'badge_workhost': 'Provider',
  'badge_freelancer': 'Searcher',
}; // fmt: skip

Map<String, Object?> configJson({
  Map<String, String> words = defaultWords,
  String min = '0.0.0',
}) => {
  'terminology': {
    'profile': words == churchWords ? 'church' : 'default',
    'terms': words,
  },
  'app': {'min_version': min, 'latest_version': '9.9.9'},
};

Map<String, Object?> meJson(String type, {String? name}) => {
  'id': 'u1',
  'user_type': type,
  'email': 'person@example.test',
  'mobile_number': '+10000000000',
  'full_name': type == 'organisation' ? null : (name ?? 'Pat Example'),
  'org_name': type == 'organisation' ? (name ?? 'Example Org') : null,
  'approval_status': null,
  'created_at': '2026-10-01T10:00:00Z',
};

class TestApp {
  TestApp(this.adapter, this.store);

  final FakeAdapter adapter;
  final MemoryTokenStore store;
}

/// Starts the whole app over a fake network. Replies must be queued on [TestApp.adapter] before
/// the first frame, or passed through [arrange].
Future<TestApp> pumpApp(
  WidgetTester tester, {
  Map<String, String> words = defaultWords,
  String minVersion = '0.0.0',
  String appVersion = '',
  void Function(FakeAdapter adapter, MemoryTokenStore store)? arrange,
  Size size = const Size(400, 800),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size * tester.view.devicePixelRatio;
  tester.platformDispatcher.textScaleFactorTestValue = textScale;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.platformDispatcher.clearAllTestValues);
  final adapter = FakeAdapter()
    ..reply(
      'GET',
      '/app/config',
      FakeReply(200, configJson(words: words, min: minVersion)),
    );
  final store = MemoryTokenStore();
  arrange?.call(adapter, store);
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
    ..httpClientAdapter = adapter;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        dioProvider.overrideWithValue(dio),
        tokenStoreProvider.overrideWithValue(store),
        appVersionProvider.overrideWithValue(appVersion),
      ],
      child: const SkillsApp(),
    ),
  );
  await tester.pumpAndSettle();
  return TestApp(adapter, store);
}

/// Types into the field with this label.
Future<void> typeInto(WidgetTester tester, String label, String value) async {
  await tester.enterText(find.widgetWithText(TextField, label), value);
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  if (finder.evaluate().isEmpty) {
    // Long lists build their rows lazily; scroll until this one exists.
    await tester.scrollUntilVisible(
      finder,
      200,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

/// Seeds a saved session, as after an app restart: only the refresh token survives.
void signedInAs(
  FakeAdapter adapter,
  MemoryTokenStore store,
  String userType, {
  String? name,
}) {
  store.save(accessToken: fresh('old'), refreshToken: fresh('r'));
  store.clearAccessForRestart();
  adapter
    ..reply(
      'POST',
      '/auth/refresh',
      FakeReply(200, tokens(fresh('a'), fresh('r'))),
    )
    ..reply('GET', '/me', FakeReply(200, meJson(userType, name: name)));
}
