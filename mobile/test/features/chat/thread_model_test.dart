import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_client.dart';
import 'package:skills_app/features/chat/data/chat_models.dart';
import 'package:skills_app/features/chat/data/chat_repository.dart';
import 'package:skills_app/features/chat/thread_model.dart';

import '../../support/fake_api.dart';
import '../../support/memory_token_store.dart';

ChatRepository _repository(FakeAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
    ..httpClientAdapter = adapter;
  final store = MemoryTokenStore()
    ..save(accessToken: fresh('a'), refreshToken: fresh('r'));
  return ChatRepository(ApiClient(dio: dio, tokens: store, appVersion: ''));
}

Map<String, Object?> _m(int seq, {String side = 'provider'}) => {
  'id': 'm$seq',
  'seq': seq,
  'conversation_id': 'c1',
  'sender_side': side,
  'body': 'text $seq',
  'created_at': '2026-11-16T10:00:00Z',
};

void main() {
  test('a client message id is a version 4 id and differs each time', () {
    final a = newClientMessageId();
    expect(
      a,
      matches(
        RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ),
      ),
    );
    expect(newClientMessageId(), isNot(a));
    expect(newClientMessageId(Random(1)), newClientMessageId(Random(1)));
  });

  test(
    'older messages are asked with the oldest seq and kept in order',
    () async {
      final adapter = FakeAdapter()
        ..reply(
          'GET',
          '/chat/conversations/c1/messages',
          FakeReply(200, [for (var i = 100; i > 50; i--) _m(i)]),
        )
        ..reply(
          'GET',
          '/chat/conversations/c1/messages',
          FakeReply(200, [_m(50), _m(49)]),
        )
        ..reply('POST', '/chat/conversations/c1/read', FakeReply(204));
      final model = ThreadModel('c1', _repository(adapter), ChatSide.starter);
      await model.load();
      expect(model.hasMore, isTrue);
      await model.loadOlder();
      expect(model.messages.map((m) => m.seq).take(3), [100, 99, 98]);
      expect(model.messages.last.seq, 49);
      expect(model.hasMore, isFalse);
      final older = adapter.seen.where((r) => r.method == 'GET').last;
      expect(older.query['before_seq'], 51);
    },
  );

  test('a message that arrives twice is shown once, in its place', () async {
    final adapter = FakeAdapter()
      ..reply(
        'GET',
        '/chat/conversations/c1/messages',
        FakeReply(200, [_m(2), _m(1)]),
      )
      ..reply('POST', '/chat/conversations/c1/read', FakeReply(204));
    final model = ThreadModel('c1', _repository(adapter), ChatSide.starter);
    await model.load();
    model.receive(ChatMessage.fromJson(_m(3)));
    model.receive(ChatMessage.fromJson(_m(3)));
    model.receive(ChatMessage.fromJson({..._m(9), 'conversation_id': 'other'}));
    expect(model.messages.map((m) => m.seq), [3, 2, 1]);
  });

  test('only messages of the other side are marked read, and once', () async {
    final adapter = FakeAdapter()
      ..reply(
        'GET',
        '/chat/conversations/c1/messages',
        FakeReply(200, [_m(3, side: 'starter'), _m(2), _m(1)]),
      )
      ..reply('POST', '/chat/conversations/c1/read', FakeReply(204));
    var changes = 0;
    final model = ThreadModel(
      'c1',
      _repository(adapter),
      ChatSide.starter,
      onReadChanged: () => changes++,
    );
    await model.load();
    await model.load();
    expect(adapter.count('POST', '/chat/conversations/c1/read'), 1);
    expect(adapter.seen.last.path, isNot('/chat/conversations/c1/read'));
    expect(changes, 1);
  });

  test('a read mark that fails is not an error on screen', () async {
    final adapter = FakeAdapter()
      ..reply('GET', '/chat/conversations/c1/messages', FakeReply(200, [_m(1)]))
      ..reply(
        'POST',
        '/chat/conversations/c1/read',
        FakeReply(500, apiError('server_error')),
      );
    final model = ThreadModel('c1', _repository(adapter), ChatSide.starter);
    await model.load();
    expect(model.error, isNull);
    expect(model.messages, hasLength(1));
  });

  test('text over the limit or empty is not sent', () async {
    final adapter = FakeAdapter()
      ..reply(
        'GET',
        '/chat/conversations/c1/messages',
        FakeReply(200, <Object?>[]),
      );
    final model = ThreadModel('c1', _repository(adapter), ChatSide.starter);
    await model.load();
    expect(model.send('  '), isFalse);
    expect(model.send('x' * (chatMaxChars + 1)), isFalse);
    expect(model.pending, isEmpty);
  });
}
