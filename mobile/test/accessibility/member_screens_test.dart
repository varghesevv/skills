import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/features/leader/leader_paths.dart';
import 'package:skills_app/features/person/person_router_paths.dart';

import '../support/fake_api.dart';
import '../support/test_app.dart';

/// Every screen a member can open, checked the same way: tap targets of 48 dp, a label on every
/// tap target, and no overflow at twice the text size on a small phone. Screens whose server
/// answers are not queued show their error state, which is checked too.
const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _page(List<Object?> items) => {
  'items': items,
  'total': items.length,
  'page': 1,
  'page_size': 10,
};

({String status, String path}) _s(String status, String path) =>
    (status: status, path: path);

final _screens = [
  _s('searcher', personHome),
  _s('provider', personHome),
  _s('verifier', personHome),
  _s('admin', personHome),
  _s('owner', personHome),
  _s('searcher', personSettings),
  _s('searcher', personAccount),
  _s('searcher', personSearch),
  _s('searcher', personRatingsGiven),
  _s('searcher', personVouches),
  _s('searcher', personNotifications),
  _s('searcher', personGroupRequests),
  _s('searcher', personMoves),
  _s('provider', personProfile),
  _s('provider', personSkills),
  _s('provider', personAvailability),
  _s('provider', personRatings),
  _s('verifier', leaderApplicants),
  _s('verifier', leaderMembers),
  _s('verifier', leaderRevoked),
  _s('verifier', leaderFlagged),
  _s('verifier', leaderInvitations),
  _s('verifier', leaderGroup),
  _s('admin', adminGroups),
];

Future<void> _open(
  WidgetTester tester,
  ({String status, String path}) screen, {
  required Size size,
  double textScale = 1.0,
}) async {
  await pumpApp(
    tester,
    size: size,
    textScale: textScale,
    arrange: (adapter, store) {
      signedInAsPerson(
        adapter,
        store,
        personJson(status: screen.status, requested: null),
      );
      adapter
        ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
        ..reply('GET', '/workhosts/me/ratings', FakeReply(200, _page([])))
        ..reply('GET', '/me/vouches', FakeReply(200, _page([])));
    },
  );
  if (screen.path != personHome) {
    ProviderScope.containerOf(tester.element(find.byType(MaterialApp)))
        .read(routerProvider)
        .go(screen.path);
    await tester.pumpAndSettle();
  }
}

void main() {
  for (final screen in _screens) {
    final name = '${screen.status} ${screen.path}';

    testWidgets('$name: tap targets are large enough and labelled', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _open(tester, screen, size: const Size(400, 800));
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      handle.dispose();
    });

    for (final brightness in [Brightness.light, Brightness.dark]) {
      testWidgets('$name: text contrast is enough in ${brightness.name} mode', (
        tester,
      ) async {
        tester.platformDispatcher.platformBrightnessTestValue = brightness;
        addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
        final handle = tester.ensureSemantics();
        await _open(tester, screen, size: const Size(400, 800));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        handle.dispose();
      });
    }

    testWidgets('$name: fits at twice the text size on a small phone', (
      tester,
    ) async {
      await _open(tester, screen, size: const Size(320, 640), textScale: 2.0);
      expect(tester.takeException(), isNull);
    });
  }
}
