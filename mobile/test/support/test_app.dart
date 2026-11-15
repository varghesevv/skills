import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
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
  'homegroup': 'Home group',
  'homegroups': 'Home groups',
  'verifier': 'Verifier',
  'verifiers': 'Verifiers',
  'admin': 'Admin',
  'admins': 'Admins',
  'owner': 'Owner',
  'owners': 'Owners',
}; // fmt: skip
const churchWords = {
  'organisation': 'Church',
  'organisations': 'Churches',
  'organisation_path': 'church',
  'organisations_path': 'churches',
  'workhost': 'Searcher',
  'workhosts': 'Searchers',
  'workhost_path': 'searcher',
  'freelancer': 'Provider',
  'freelancers': 'Providers',
  'freelancer_path': 'provider',
  'freelancers_path': 'providers',
  'badge_organisation': 'Church',
  'badge_workhost': 'Searcher',
  'badge_freelancer': 'Provider',
  'homegroup': 'Home group',
  'homegroups': 'Home groups',
  'verifier': 'Group leader',
  'verifiers': 'Group leaders',
  'admin': 'Church admin',
  'admins': 'Church admins',
  'owner': 'Owner',
  'owners': 'Owners',
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

Map<String, Object?> personJson({
  String status = 'pending',
  String? requested = 'searcher',
  String name = 'Nadia Applicant',
  int vouches = 0,
  Map<String, Object?>? group = const {'id': 'group-1', 'name': 'Riverside'},
  String? leader = 'Lena Leader',
  String id = 'p1',
}) => {
  'user_type': 'person',
  'id': id,
  'full_name': name,
  'email': 'nadia@example.test',
  'mobile_number': '+10000000001',
  'status': status,
  'requested_status': requested,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': group,
  'leader': leader == null ? null : {'name': leader},
  'status_set_by': null,
  'flagged_for_recheck': false,
  'vouch_count': vouches,
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
  List<Override> overrides = const [],
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
    appRoot(
      overrides: [
        dioProvider.overrideWithValue(dio),
        tokenStoreProvider.overrideWithValue(store),
        appVersionProvider.overrideWithValue(appVersion),
        ...overrides,
      ],
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

/// Seeds a saved session of a PROVIDER whose id is `u1`, with no notifications, so the home page
/// can be opened and the provider pages reached through their tiles.
void signedInAsProvider(FakeAdapter adapter, MemoryTokenStore store) {
  signedInAsPerson(
    adapter,
    store,
    personJson(
      status: 'provider',
      requested: null,
      id: 'u1',
      name: 'Pat Example',
    ),
  );
  adapter.reply(
    'GET',
    '/me/notifications',
    FakeReply(200, {'items': [], 'total': 0, 'unread_count': 0}),
  );
}

/// Seeds a saved session of a person of the church trust model.
void signedInAsPerson(
  FakeAdapter adapter,
  MemoryTokenStore store, [
  Map<String, Object?>? person,
]) {
  store.save(accessToken: fresh('old'), refreshToken: fresh('r'));
  store.clearAccessForRestart();
  adapter
    ..reply(
      'POST',
      '/auth/refresh',
      FakeReply(200, tokens(fresh('a'), fresh('r'))),
    )
    ..reply('GET', '/me', FakeReply(200, person ?? personJson()));
}

/// Answers the date picker with prepared moments, in order, instead of showing the dial.
class FakePicker {
  FakePicker(List<DateTime?> answers) : _answers = [...answers];

  final List<DateTime?> _answers;
  final asked = <DateTime?>[]; // the initial value each call was given

  Future<DateTime?> call(BuildContext context, DateTime? initial) async {
    asked.add(initial);
    return _answers.isEmpty ? null : _answers.removeAt(0);
  }
}
