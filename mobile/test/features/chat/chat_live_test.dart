import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/fake_chat_link.dart';
import '../../support/test_app.dart';

Map<String, Object?> _conversation({int unread = 0, bool closed = false}) => {
  'id': 'c1',
  'my_side': 'starter',
  'other': {
    'id': 'prov-1',
    'full_name': closed ? null : 'Anita Provider',
    'closed': closed,
  },
  'last_message_preview': 'Hello',
  'last_message_at': '2026-11-16T10:00:00Z',
  'unread_count': unread,
  'muted': false,
  'blocked': false,
};

Map<String, Object?> _message(
  int seq,
  String body, {
  String side = 'provider',
}) => {
  'id': 'm$seq',
  'seq': seq,
  'conversation_id': 'c1',
  'sender_side': side,
  'body': body,
  'created_at': '2026-11-16T10:0$seq:00Z',
};

String _ready() =>
    jsonEncode({'type': 'ready', 'server_time': 'x', 'heartbeat_seconds': 25});

Future<({TestApp app, FakeServer server})> _open(WidgetTester tester) async {
  final server = FakeServer();
  final app = await pumpApp(
    tester,
    size: const Size(400, 1200),
    chatConnector: server.connect,
    arrange: (adapter, store) {
      signedInAsPerson(
        adapter,
        store,
        personJson(status: 'searcher', requested: null, id: 'p1'),
      );
      adapter
        ..reply(
          'GET',
          '/me/notifications',
          FakeReply(200, {'items': [], 'total': 0, 'unread_count': 0}),
        )
        ..reply('GET', '/chat/unread', FakeReply(200, {'total': 0}))
        ..reply(
          'GET',
          '/chat/conversations',
          FakeReply(200, {
            'items': [_conversation()],
            'total': 1,
            'page': 1,
            'page_size': 50,
          }),
        )
        ..reply(
          'GET',
          '/chat/conversations/c1',
          FakeReply(200, _conversation()),
        )
        ..reply(
          'GET',
          '/chat/conversations/c1/messages',
          FakeReply(200, [_message(1, 'Hello')]),
        )
        ..reply('POST', '/chat/conversations/c1/read', FakeReply(204));
    },
  );
  return (app: app, server: server);
}

Future<void> _connect(WidgetTester tester, FakeServer server) async {
  await tester.pump();
  expect(server.links, isNotEmpty);
  server.last.say(_ready());
  await tester.pump();
}

void main() {
  testWidgets('a signed-in member connects with the token in the first frame', (
    tester,
  ) async {
    final (:app, :server) = await _open(tester);
    await _connect(tester, server);
    expect(server.addresses.single.query, isEmpty);
    final first = jsonDecode(server.last.sent.first) as Map;
    expect(first['type'], 'auth');
    expect(first['token'], isNotEmpty);
  });

  testWidgets(
    'a new message updates the unread count and is acknowledged as delivered',
    (tester) async {
      final (:app, :server) = await _open(tester);
      await _connect(tester, server);
      app.adapter
        ..setReply('GET', '/chat/unread', FakeReply(200, {'total': 1}))
        ..setReply(
          'GET',
          '/chat/conversations',
          FakeReply(200, {
            'items': [_conversation(unread: 1)],
            'total': 1,
            'page': 1,
            'page_size': 50,
          }),
        );
      server.last.say(
        jsonEncode({
          'type': 'message',
          'message': _message(2, 'Are you free?'),
        }),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('1 unread message'), findsOneWidget);
      final frames = server.last.sent.map((f) => jsonDecode(f) as Map).toList();
      expect(frames.last, {
        'type': 'delivered',
        'conversation_id': 'c1',
        'up_to_seq': 2,
      });
    },
  );

  testWidgets('a message shows in the open thread at once, and once', (
    tester,
  ) async {
    final (:app, :server) = await _open(tester);
    await _connect(tester, server);
    await tapKey(tester, 'messages');
    await tester.tap(find.byKey(const Key('conversation-c1')));
    await tester.pumpAndSettle();
    final frame = jsonEncode({
      'type': 'message',
      'message': _message(2, 'Live hello'),
    });
    server.last.say(frame);
    server.last.say(frame);
    await tester.pumpAndSettle();
    expect(find.text('Live hello'), findsOneWidget);
  });

  testWidgets(
    'a screen reader hears a new message from the other person, once',
    (tester) async {
      final heard = <String>[];
      tester.binding.defaultBinaryMessenger
          .setMockDecodedMessageHandler<Object?>(SystemChannels.accessibility, (
            message,
          ) async {
            final map = message as Map;
            if (map['type'] == 'announce') {
              heard.add((map['data'] as Map)['message'] as String);
            }
            return null;
          });
      addTearDown(
        () => tester.binding.defaultBinaryMessenger
            .setMockDecodedMessageHandler<Object?>(
              SystemChannels.accessibility,
              null,
            ),
      );
      final (:app, :server) = await _open(tester);
      await _connect(tester, server);
      await tapKey(tester, 'messages');
      await tester.tap(find.byKey(const Key('conversation-c1')));
      await tester.pumpAndSettle();
      final theirs = jsonEncode({
        'type': 'message',
        'message': _message(2, 'Are you free?'),
      });
      server.last.say(theirs);
      server.last.say(theirs);
      server.last.say(
        jsonEncode({
          'type': 'message',
          'message': _message(3, 'My own words', side: 'starter'),
        }),
      );
      await tester.pumpAndSettle();
      expect(heard, ['New message from Anita Provider: Are you free?']);
    },
  );

  testWidgets(
    'a message of another conversation does not appear in the open thread',
    (tester) async {
      final (:app, :server) = await _open(tester);
      await _connect(tester, server);
      await tapKey(tester, 'messages');
      await tester.tap(find.byKey(const Key('conversation-c1')));
      await tester.pumpAndSettle();
      server.last.say(
        jsonEncode({
          'type': 'message',
          'message': {
            ..._message(7, 'Meant for someone else'),
            'conversation_id': 'c2',
          },
        }),
      );
      await tester.pumpAndSettle();
      expect(find.text('Meant for someone else'), findsNothing);
    },
  );

  testWidgets('after a reconnect the open thread reads its messages again', (
    tester,
  ) async {
    final (:app, :server) = await _open(tester);
    await _connect(tester, server);
    await tapKey(tester, 'messages');
    await tester.tap(find.byKey(const Key('conversation-c1')));
    await tester.pumpAndSettle();
    final before = app.adapter.count('GET', '/chat/conversations/c1/messages');
    app.adapter.setReply(
      'GET',
      '/chat/conversations/c1/messages',
      FakeReply(200, [_message(2, 'Missed while away'), _message(1, 'Hello')]),
    );
    await server.last.drop();
    await tester.pump(const Duration(seconds: 3));
    server.last.say(_ready());
    await tester.pumpAndSettle();
    expect(
      app.adapter.count('GET', '/chat/conversations/c1/messages'),
      before + 1,
    );
    expect(find.text('Missed while away'), findsOneWidget);
  });

  testWidgets(
    'the socket is closed in the background and opened again on return',
    (tester) async {
      final (:app, :server) = await _open(tester);
      await _connect(tester, server);
      expect(server.links.length, 1);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      expect(server.links.first.closedByClient, isTrue);
      await tester.pump(const Duration(minutes: 2));
      expect(server.links.length, 1); // nothing is tried in the background
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(server.links.length, 2);
    },
  );

  testWidgets('logging out closes the socket', (tester) async {
    final (:app, :server) = await _open(tester);
    await _connect(tester, server);
    app.adapter.reply('POST', '/auth/logout', FakeReply(204));
    await tapKey(tester, 'log-out');
    await tester.pumpAndSettle();
    expect(server.links.first.closedByClient, isTrue);
  });

  testWidgets('an applicant does not open a socket', (tester) async {
    final server = FakeServer();
    await pumpApp(
      tester,
      chatConnector: server.connect,
      arrange: (adapter, store) =>
          signedInAsPerson(adapter, store, personJson()),
    );
    await tester.pump();
    expect(server.addresses, isEmpty);
  });
}
