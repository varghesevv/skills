import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/providers.dart';
import 'package:skills_app/features/chat/chat_providers.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _noNotes = {'items': [], 'total': 0, 'unread_count': 0};

Map<String, Object?> _conversation({
  String id = 'c1',
  String mySide = 'starter',
  String? name = 'Anita Provider',
  bool closed = false,
  int unread = 2,
  bool muted = false,
  bool blocked = false,
}) => {
  'id': id,
  'my_side': mySide,
  'other': {'id': 'prov-1', 'full_name': name, 'closed': closed},
  'last_message_preview': 'See you on Tuesday',
  'last_message_at': '2026-11-16T10:00:00Z',
  'unread_count': unread,
  'muted': muted,
  'blocked': blocked,
};

Map<String, Object?> _message(
  int seq,
  String body, {
  String side = 'provider',
  String id = '',
}) => {
  'id': id.isEmpty ? 'm$seq' : id,
  'seq': seq,
  'conversation_id': 'c1',
  'sender_side': side,
  'body': body,
  'created_at': '2026-11-16T10:${seq.toString().padLeft(2, '0')}:00Z',
};

Map<String, Object?> _page(List<Map<String, Object?>> items) => {
  'items': items,
  'total': items.length,
  'page': 1,
  'page_size': 50,
};

Future<TestApp> _open(
  WidgetTester tester, {
  String status = 'searcher',
  Map<String, Object?>? conversation,
  void Function(FakeAdapter adapter)? arrange,
}) => pumpApp(
  tester,
  size: const Size(400, 1200),
  arrange: (adapter, store) {
    signedInAsPerson(
      adapter,
      store,
      personJson(status: status, requested: null, id: 'p1'),
    );
    adapter
      ..reply('GET', '/me/notifications', FakeReply(200, _noNotes))
      ..reply('GET', '/chat/unread', FakeReply(200, {'total': 2}))
      ..reply(
        'GET',
        '/chat/conversations',
        FakeReply(200, _page([conversation ?? _conversation()])),
      )
      ..reply(
        'GET',
        '/chat/conversations/c1',
        FakeReply(200, conversation ?? _conversation()),
      )
      ..reply(
        'GET',
        '/chat/conversations/c1/messages',
        FakeReply(200, [
          _message(2, 'See you on Tuesday'),
          _message(1, 'Hello'),
        ]),
      )
      ..reply('POST', '/chat/conversations/c1/read', FakeReply(204))
      ..reply('GET', '/freelancers', FakeReply(200, {}));
    arrange?.call(adapter);
  },
);

Future<void> _openThread(WidgetTester tester) async {
  await tapKey(tester, 'messages');
  await tester.tap(find.byKey(const Key('conversation-c1')));
  await tester.pumpAndSettle();
}

void main() {
  test('messages are for a searcher or above', () {
    PersonMe of(String s) => PersonMe.fromJson(personJson(status: s));
    for (final path in ['/member/chat', '/member/chat/c1']) {
      expect(personMayVisit(of('searcher'), path), isTrue);
      expect(personMayVisit(of('provider'), path), isTrue);
      expect(personMayVisit(of('pending'), path), isFalse);
      expect(personMayVisit(of('revoked'), path), isFalse);
    }
  });

  testWidgets('the home shows how many messages are unread', (tester) async {
    await _open(tester);
    expect(find.textContaining('2 unread message'), findsOneWidget);
  });

  testWidgets('the list shows the other person, the preview and unread', (
    tester,
  ) async {
    await _open(tester);
    await tapKey(tester, 'messages');
    expect(find.text('Anita Provider'), findsOneWidget);
    expect(find.text('See you on Tuesday'), findsOneWidget);
    expect(find.text('2'), findsWidgets);
  });

  testWidgets('a conversation with a closed account shows no name', (
    tester,
  ) async {
    await _open(
      tester,
      conversation: _conversation(name: null, closed: true, unread: 0),
    );
    await _openThread(tester);
    expect(find.text('Closed account'), findsWidgets);
    expect(find.byKey(const Key('message-input')), findsNothing);
    expect(
      find.text('This person can no longer be written to.'),
      findsOneWidget,
    );
  });

  testWidgets('opening a thread shows the messages and marks them read', (
    tester,
  ) async {
    final app = await _open(tester);
    await _openThread(tester);
    expect(find.text('Hello'), findsOneWidget);
    expect(find.text('See you on Tuesday'), findsWidgets);
    final read = app.adapter.seen.where(
      (r) => r.path == '/chat/conversations/c1/read',
    );
    expect(read.single.body, {'up_to_seq': 2});
  });

  testWidgets('sending trims the text, keeps one id and shows the message', (
    tester,
  ) async {
    final app = await _open(
      tester,
      arrange: (adapter) => adapter.reply(
        'POST',
        '/chat/conversations/c1/messages',
        FakeReply(201, _message(3, 'On my way', side: 'starter')),
      ),
    );
    await _openThread(tester);
    await tester.enterText(
      find.byKey(const Key('message-input')),
      '  On my way  ',
    );
    await tester.tap(find.byKey(const Key('send')));
    await tester.pumpAndSettle();
    final sent = app.adapter.seen.singleWhere(
      (r) => r.method == 'POST' && r.path == '/chat/conversations/c1/messages',
    );
    final body = sent.body! as Map;
    expect(body['body'], 'On my way');
    expect(body['client_message_id'], matches(RegExp(r'^[0-9a-f-]{36}$')));
    expect(find.text('On my way'), findsOneWidget);
    expect(find.byKey(const Key('retry-send')), findsNothing);
    final field = tester.widget<TextField>(
      find.byKey(const Key('message-input')),
    );
    expect(field.controller!.text, isEmpty);
  });

  testWidgets('an empty message is not sent', (tester) async {
    final app = await _open(tester);
    await _openThread(tester);
    await tester.enterText(find.byKey(const Key('message-input')), '   ');
    await tester.tap(find.byKey(const Key('send')));
    await tester.pumpAndSettle();
    expect(app.adapter.count('POST', '/chat/conversations/c1/messages'), 0);
  });

  testWidgets('a failed send can be sent again with the same id', (
    tester,
  ) async {
    final app = await _open(
      tester,
      arrange: (adapter) => adapter
        ..reply(
          'POST',
          '/chat/conversations/c1/messages',
          FakeReply(429, apiError('chat_rate_limited')),
        )
        ..reply(
          'POST',
          '/chat/conversations/c1/messages',
          FakeReply(201, _message(3, 'Again', side: 'starter')),
        ),
    );
    await _openThread(tester);
    await tester.enterText(find.byKey(const Key('message-input')), 'Again');
    await tester.tap(find.byKey(const Key('send')));
    await tester.pumpAndSettle();
    expect(find.textContaining('too fast'), findsOneWidget);
    await tester.tap(find.byKey(const Key('retry-send')));
    await tester.pumpAndSettle();
    final posts = app.adapter.seen
        .where((r) => r.method == 'POST' && r.path.endsWith('/messages'))
        .map((r) => (r.body! as Map)['client_message_id'])
        .toList();
    expect(posts.length, 2);
    expect(posts[0], posts[1]);
    expect(find.byKey(const Key('retry-send')), findsNothing);
    expect(find.text('Again'), findsOneWidget);
  });

  testWidgets('a person can discard a message that did not go', (tester) async {
    await _open(
      tester,
      arrange: (adapter) => adapter.reply(
        'POST',
        '/chat/conversations/c1/messages',
        FakeReply(403, apiError('chat_blocked')),
      ),
    );
    await _openThread(tester);
    await tester.enterText(find.byKey(const Key('message-input')), 'Hi');
    await tester.tap(find.byKey(const Key('send')));
    await tester.pumpAndSettle();
    expect(find.text('You cannot write to this person.'), findsOneWidget);
    await tester.tap(find.byKey(const Key('discard-send')));
    await tester.pumpAndSettle();
    expect(find.text('Hi'), findsNothing);
  });

  testWidgets('only the provider side may block, and muting is for both', (
    tester,
  ) async {
    await _open(tester);
    await _openThread(tester);
    await tester.tap(find.byKey(const Key('chat-menu')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('menu-mute')), findsOneWidget);
    expect(find.byKey(const Key('menu-block')), findsNothing);
    expect(find.byKey(const Key('menu-report')), findsOneWidget);
  });

  testWidgets('a provider can block, and the composer is replaced', (
    tester,
  ) async {
    final app = await _open(
      tester,
      status: 'provider',
      conversation: _conversation(mySide: 'provider'),
      arrange: (adapter) => adapter.reply(
        'PUT',
        '/chat/conversations/c1/settings',
        FakeReply(
          200,
          _conversation(mySide: 'provider', blocked: true, unread: 0),
        ),
      ),
    );
    await _openThread(tester);
    await tester.tap(find.byKey(const Key('chat-menu')));
    await tester.pumpAndSettle();
    // The server now says blocked, as the refreshed list will show.
    app.adapter.setReply(
      'GET',
      '/chat/conversations',
      FakeReply(
        200,
        _page([_conversation(mySide: 'provider', blocked: true, unread: 0)]),
      ),
    );
    await tester.tap(find.byKey(const Key('menu-block')));
    await tester.pumpAndSettle();
    final put = app.adapter.seen.singleWhere((r) => r.method == 'PUT');
    expect(put.body, {'blocked': true});
    expect(find.byKey(const Key('message-input')), findsNothing);
    expect(find.textContaining('You blocked this person'), findsOneWidget);
  });

  testWidgets('a conversation can be reported with a reason', (tester) async {
    final app = await _open(
      tester,
      arrange: (adapter) => adapter.reply(
        'POST',
        '/chat/conversations/c1/report',
        FakeReply(201, {
          'id': 'r1',
          'reason': 'scam',
          'note': null,
          'created_at': '2026-11-16T10:00:00Z',
        }),
      ),
    );
    await _openThread(tester);
    await tester.tap(find.byKey(const Key('chat-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('menu-report')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('report-scam')));
    await tester.pumpAndSettle();
    final post = app.adapter.seen.singleWhere(
      (r) => r.path == '/chat/conversations/c1/report',
    );
    expect(post.body, {'reason': 'scam'});
    expect(find.text('Reported. Thank you.'), findsOneWidget);
  });

  testWidgets('a conversation outside the first page of the list opens', (
    tester,
  ) async {
    await _open(
      tester,
      arrange: (adapter) => adapter.setReply(
        'GET',
        '/chat/conversations',
        FakeReply(200, _page([_conversation(id: 'other', name: 'Someone')])),
      ),
    );
    final router = ProviderScope.containerOf(
      tester.element(find.byType(MaterialApp)),
    ).read(routerProvider);
    router.go('/member/chat/c1');
    await tester.pumpAndSettle();
    expect(find.text('Anita Provider'), findsWidgets);
    expect(find.byKey(const Key('message-input')), findsOneWidget);
  });

  testWidgets('a conversation that is not the person\'s says so', (
    tester,
  ) async {
    await _open(
      tester,
      arrange: (adapter) => adapter.setReply(
        'GET',
        '/chat/conversations/c1',
        FakeReply(404, apiError('not_found')),
      ),
    );
    await _openThread(tester);
    expect(find.text('This conversation is not available.'), findsOneWidget);
    expect(find.text('Try again'), findsNothing);
    expect(find.byKey(const Key('message-input')), findsNothing);
  });

  testWidgets(
    'a failed refresh of the list keeps the open thread and its text',
    (tester) async {
      await _open(tester);
      await _openThread(tester);
      await tester.enterText(find.byKey(const Key('message-input')), 'Draft');
      final container = ProviderScope.containerOf(
        tester.element(find.byType(MaterialApp)),
      );
      final adapter =
          (container.read(dioProvider).httpClientAdapter) as FakeAdapter;
      adapter.setReply(
        'GET',
        '/chat/conversations',
        FakeReply(503, apiError('service_unavailable')),
      );
      container.invalidate(conversationsProvider);
      await tester.pumpAndSettle();
      expect(find.text('Draft'), findsOneWidget);
      expect(find.byKey(const Key('message-input')), findsOneWidget);
    },
  );

  testWidgets('a change seen in the list reaches the open thread', (
    tester,
  ) async {
    await _open(tester);
    await _openThread(tester);
    expect(find.byKey(const Key('message-input')), findsOneWidget);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(MaterialApp)),
    );
    final adapter =
        (container.read(dioProvider).httpClientAdapter) as FakeAdapter;
    adapter.setReply(
      'GET',
      '/chat/conversations',
      FakeReply(
        200,
        _page([_conversation(name: null, closed: true, unread: 0)]),
      ),
    );
    container.invalidate(conversationsProvider);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('message-input')), findsNothing);
    expect(find.text('Closed account'), findsWidgets);
  });

  testWidgets('older messages that cannot be loaded say so', (tester) async {
    await _open(
      tester,
      arrange: (adapter) => adapter
        ..setReply(
          'GET',
          '/chat/conversations/c1/messages',
          FakeReply(200, [
            for (var i = 50; i >= 1; i--) _message(i, 'm$i', id: 'x$i'),
          ]),
        ),
    );
    await _openThread(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(MaterialApp)),
    );
    final adapter =
        (container.read(dioProvider).httpClientAdapter) as FakeAdapter;
    adapter.setReply(
      'GET',
      '/chat/conversations/c1/messages',
      FakeReply(503, apiError('service_unavailable')),
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('older')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('older')));
    await tester.pumpAndSettle();
    expect(find.textContaining('temporarily unavailable'), findsOneWidget);
    expect(find.text('m1'), findsOneWidget); // what was loaded stays
  });

  testWidgets('an empty list says how to start', (tester) async {
    await _open(
      tester,
      arrange: (adapter) => adapter.setReply(
        'GET',
        '/chat/conversations',
        FakeReply(200, _page([])),
      ),
    );
    await tapKey(tester, 'messages');
    expect(find.textContaining('no messages yet'), findsOneWidget);
    expect(find.textContaining('Open a freelancer'), findsOneWidget);
  });
}
