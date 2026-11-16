import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/features/chat/chat_paths.dart';
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

typedef _Screen = ({
  String status,
  String path,
  Object? extra,
  void Function(FakeAdapter adapter)? arrange,
});

_Screen _s(
  String status,
  String path, {
  Object? extra,
  void Function(FakeAdapter adapter)? arrange,
}) => (status: status, path: path, extra: extra, arrange: arrange);

/// The answers of the screens that take an id or a token.
Map<String, Object?> _provider() => {
  'id': 'p1',
  'full_name': 'Anita Provider',
  'whatsapp_availability': true,
  'nationality': 'Examplean',
  'primary_language': 'English',
  'rate_per_hour': 45.5,
  'rate_currency': 'AED',
  'is_rate_negotiable': true,
  'labels': <Object?>[],
  'average_rating': 8.5,
  'rating_count': 4,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'unavailable': <Object?>[],
  'my_rating': null,
};

Map<String, Object?> _detail() => {
  'id': 'a1',
  'full_name': 'Nadia Applicant',
  'mobile_number': '+971 50 123 4567',
  'status': 'pending',
  'requested_status': 'provider',
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'status_set_by': null,
  'flagged_for_recheck': false,
  'applied_at': '2026-11-10T08:00:00Z',
  'history': <Object?>[],
  'chain_of_trust': [
    {'id': 'p9', 'full_name': 'Lena Leader', 'status': 'verifier'},
  ],
  'vouches': <Object?>[],
  'can_admit_as_provider': true,
};

Map<String, Object?> _conversation() => {
  'id': 'c1',
  'my_side': 'starter',
  'other': {'id': 'p9', 'full_name': 'Anita Provider', 'closed': false},
  'last_message_preview': 'See you on Tuesday',
  'last_message_at': '2026-11-16T10:00:00Z',
  'unread_count': 2,
  'muted': false,
  'blocked': false,
};

void _chat(FakeAdapter a) => a
  ..reply('GET', '/chat/unread', FakeReply(200, {'total': 2}))
  ..reply('GET', '/chat/conversations/c1', FakeReply(200, _conversation()))
  ..reply(
    'GET',
    '/chat/conversations',
    FakeReply(200, _page([_conversation()])),
  )
  ..reply('POST', '/chat/conversations/c1/read', FakeReply(204))
  ..reply(
    'GET',
    '/chat/conversations/c1/messages',
    FakeReply(200, [
      {
        'id': 'm2',
        'seq': 2,
        'conversation_id': 'c1',
        'sender_side': 'provider',
        'body': 'See you on Tuesday',
        'created_at': '2026-11-16T10:00:00Z',
      },
      {
        'id': 'm1',
        'seq': 1,
        'conversation_id': 'c1',
        'sender_side': 'starter',
        'body': 'Hello',
        'created_at': '2026-11-16T09:00:00Z',
      },
    ]),
  );

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
  _s('searcher', chatList, arrange: _chat),
  _s('searcher', chatThread('c1'), arrange: _chat),
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
  _s(
    'searcher',
    '$personProviders/p1',
    arrange: (a) => a
      ..reply('GET', '/freelancers/p1', FakeReply(200, _provider()))
      ..reply('GET', '/freelancers/p1/ratings', FakeReply(200, _page([]))),
  ),
  _s(
    'verifier',
    '$leaderPeople/a1',
    arrange: (a) =>
        a.reply('GET', '/verifier/people/a1', FakeReply(200, _detail())),
  ),
  _s(
    'searcher',
    vouchLinkPath,
    extra: 'a-vouch-token-of-enough-length-1234567890',
    arrange: (a) => a.reply(
      'POST',
      '/vouch-links/lookup',
      FakeReply(200, {
        'applicant_name': 'Nadia Applicant',
        'church_name': 'Grace Church',
        'home_group_name': 'Riverside',
        'requested_status': 'provider',
        'already_vouched': false,
      }),
    ),
  ),
];

Future<void> _open(
  WidgetTester tester,
  _Screen screen, {
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
      screen.arrange?.call(adapter);
    },
  );
  if (screen.path != personHome) {
    final router = ProviderScope.containerOf(
      tester.element(find.byType(MaterialApp)),
    ).read(routerProvider);
    router.go(screen.path, extra: screen.extra);
    await tester.pumpAndSettle();
    // The screen is the one on show, not the home the router sends a person to otherwise.
    expect(
      router.routerDelegate.currentConfiguration.last.matchedLocation,
      screen.path,
    );
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
