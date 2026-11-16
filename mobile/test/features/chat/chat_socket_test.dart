import 'dart:convert';
import 'dart:math';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/features/chat/live/chat_events.dart';
import 'package:skills_app/features/chat/live/chat_live.dart';
import 'package:skills_app/features/chat/live/chat_socket.dart';

import '../../support/fake_api.dart';
import '../../support/fake_chat_link.dart';

/// No jitter, so that waits are exact.
class _NoJitter implements Random {
  @override
  bool nextBool() => false;
  @override
  double nextDouble() => 0;
  @override
  int nextInt(int max) => 0;
}

class _Rig {
  _Rig({int failures = 0, this.renews = true})
    : server = FakeServer(failures: failures) {
    socket = ChatSocket(
      address: Uri.parse('wss://api.test/api/v1/chat/ws'),
      connector: server.connect,
      accessToken: () async => token,
      renewSession: () async {
        renewals++;
        if (renews) token = fresh('renewed');
        return renews;
      },
      random: _NoJitter(),
    );
    socket.events.listen(events.add);
  }

  final FakeServer server;
  final bool renews;
  late final ChatSocket socket;
  String? token = fresh('access');
  int renewals = 0;
  final events = <ChatEvent>[];

  Map<String, Object?> sentFrame(int link, int index) =>
      jsonDecode(server.links[link].sent[index]) as Map<String, Object?>;
}

String _ready() => jsonEncode({
  'type': 'ready',
  'server_time': '2026-11-16T10:00:00Z',
  'heartbeat_seconds': 25,
});

Map<String, Object?> _message(int seq) => {
  'id': 'm$seq',
  'seq': seq,
  'conversation_id': 'c1',
  'sender_side': 'provider',
  'body': 'text $seq',
  'created_at': '2026-11-16T10:00:00Z',
};

void main() {
  test('the address is wss for https and the token is not in it', () {
    expect(
      chatSocketUri('https://demo.example.org/api/v1').toString(),
      'wss://demo.example.org/api/v1/chat/ws',
    );
    expect(
      chatSocketUri('http://10.0.2.2:8000/api/v1/').toString(),
      'ws://10.0.2.2:8000/api/v1/chat/ws',
    );
  });

  test('the token goes in the first frame and the connection is ready after the answer', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      expect(rig.server.addresses.single.query, isEmpty);
      expect(rig.sentFrame(0, 0), {'type': 'auth', 'token': rig.token});
      expect(rig.socket.status, ChatSocketStatus.connecting);
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      expect(rig.socket.status, ChatSocketStatus.connected);
      expect((rig.events.single as ChatConnected).again, isFalse);
    });
  });

  test('a ping goes out every 25 seconds while connected', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 26));
      expect(rig.sentFrame(0, 1), {'type': 'ping'});
      rig.server.last.say('{"type":"pong"}');
      async.elapse(const Duration(seconds: 25));
      expect(rig.server.links[0].sent.length, 3);
    });
  });

  test(
    'messages and marks become events; broken or unknown frames are skipped',
    () {
      fakeAsync((async) {
        final rig = _Rig()..socket.start();
        async.flushMicrotasks();
        final link = rig.server.last..say(_ready());
        link
          ..say(jsonEncode({'type': 'message', 'message': _message(4)}))
          ..say(
            jsonEncode({
              'type': 'read',
              'conversation_id': 'c1',
              'side': 'provider',
              'up_to_seq': 4,
            }),
          )
          ..say(
            jsonEncode({
              'type': 'delivered',
              'conversation_id': 'c1',
              'side': 'starter',
              'up_to_seq': 3,
            }),
          )
          ..say(jsonEncode({'type': 'error', 'code': 'chat_blocked'}))
          ..say('not json')
          ..say('[1,2]')
          ..say(
            jsonEncode({
              'type': 'message',
              'message': {'id': 1},
            }),
          )
          ..say(jsonEncode({'type': 'read', 'side': 'nobody'}))
          ..say(jsonEncode({'type': 'surprise'}));
        async.flushMicrotasks();
        expect(rig.events.length, 5);
        expect((rig.events[1] as ChatMessageEvent).message.seq, 4);
        final read = rig.events[2] as ChatMarkEvent;
        expect((read.read, read.conversationId, read.upToSeq), (true, 'c1', 4));
        expect((rig.events[3] as ChatMarkEvent).read, isFalse);
        expect((rig.events[4] as ChatErrorEvent).code, 'chat_blocked');
        expect(rig.socket.status, ChatSocketStatus.connected);
      });
    },
  );

  test('delivered is sent only while connected', () {
    fakeAsync((async) {
      final rig = _Rig();
      rig.socket.delivered('c1', 1); // not started
      rig.socket.start();
      async.flushMicrotasks();
      rig.socket.delivered('c1', 2); // not ready yet
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      rig.socket.delivered('c1', 5);
      final frames = rig.server.last.sent.map(jsonDecode).toList();
      expect(frames.length, 2); // auth and one delivered
      expect(frames[1], {
        'type': 'delivered',
        'conversation_id': 'c1',
        'up_to_seq': 5,
      });
    });
  });

  test('a lost connection is retried after 1, 2, 4 seconds and says it is a reconnect', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      rig.server.last.drop();
      async.flushMicrotasks();
      expect(rig.socket.status, ChatSocketStatus.waiting);
      expect(rig.events.last, isA<ChatDisconnected>());
      async.elapse(const Duration(milliseconds: 900));
      expect(rig.server.links.length, 1);
      async.elapse(const Duration(milliseconds: 200));
      expect(rig.server.links.length, 2);
      // The new connection never answers: wait 2 s, then 4 s.
      async.elapse(const Duration(seconds: 10));
      expect(rig.server.links.length, 2);
      async.elapse(const Duration(seconds: 3));
      expect(rig.server.links.length, 3);
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      expect((rig.events.last as ChatConnected).again, isTrue);
    });
  });

  test(
    'a server that cannot be reached is tried again, with growing waits',
    () {
      fakeAsync((async) {
        final rig = _Rig(failures: 3)..socket.start();
        async.flushMicrotasks();
        expect(rig.server.addresses.length, 1);
        async.elapse(const Duration(seconds: 1));
        expect(rig.server.addresses.length, 2);
        async.elapse(const Duration(seconds: 2));
        expect(rig.server.addresses.length, 3);
        async.elapse(const Duration(seconds: 4));
        expect(rig.server.addresses.length, 4);
        expect(rig.server.links.length, 1);
      });
    },
  );

  test('the wait never grows past the limit', () {
    fakeAsync((async) {
      final rig = _Rig(failures: 100)..socket.start();
      async.elapse(const Duration(minutes: 5));
      // 1+2+4+8+16 s, then every 30 s: well under one attempt per 20 s on average.
      expect(rig.server.addresses.length, lessThan(15));
      expect(rig.server.addresses.length, greaterThan(8));
    });
  });

  test(
    'a connection that is silent for 70 seconds is dropped and reopened',
    () {
      fakeAsync((async) {
        final rig = _Rig()..socket.start();
        async.flushMicrotasks();
        rig.server.last.say(_ready());
        async.flushMicrotasks();
        async.elapse(const Duration(seconds: 71));
        expect(rig.server.links[0].closedByClient, isTrue);
        async.elapse(const Duration(seconds: 2));
        expect(rig.server.links.length, 2);
      });
    },
  );

  test('a server that never says ready is given up on and tried again', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 11));
      expect(rig.server.links[0].closedByClient, isTrue);
      async.elapse(const Duration(seconds: 2));
      expect(rig.server.links.length, 2);
    });
  });

  test('an expired token (4401) renews the session and reconnects at once with the new one', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      final first = rig.token;
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      rig.server.links[0].serverClose(4401);
      async.flushMicrotasks();
      expect(rig.renewals, 1);
      expect(rig.server.links.length, 2);
      expect(rig.sentFrame(1, 0)['token'], rig.token);
      expect(rig.token, isNot(first));
    });
  });

  test(
    'when the session cannot be renewed the socket stops and does not hammer',
    () {
      fakeAsync((async) {
        final rig = _Rig(renews: false)..socket.start();
        async.flushMicrotasks();
        rig.server.last.say(_ready());
        async.flushMicrotasks();
        rig.server.links[0].serverClose(4401);
        async.flushMicrotasks();
        async.elapse(const Duration(minutes: 5));
        expect(rig.server.links.length, 1);
        expect(rig.socket.status, ChatSocketStatus.stopped);
      });
    },
  );

  test('a second 4401 in a row waits instead of looping', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.links[0].serverClose(4401);
      async.flushMicrotasks();
      rig.server.links[1].serverClose(4401); // the new token is refused too
      async.flushMicrotasks();
      expect(rig.renewals, 1);
      expect(rig.socket.status, ChatSocketStatus.waiting);
    });
  });

  test('4403 means this person may not chat: nothing is tried again', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      rig.server.links[0].serverClose(4403);
      async.flushMicrotasks();
      async.elapse(const Duration(minutes: 5));
      expect(rig.server.links.length, 1);
      expect(rig.socket.status, ChatSocketStatus.denied);
      rig.socket.start(); // asked again (the app came back): it tries once more
      async.flushMicrotasks();
      expect(rig.server.links.length, 2);
    });
  });

  test('4429 waits half a minute', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.links[0].serverClose(4429);
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 29));
      expect(rig.server.links.length, 1);
      async.elapse(const Duration(seconds: 2));
      expect(rig.server.links.length, 2);
    });
  });

  test('without an access token the session is renewed first', () {
    fakeAsync((async) {
      final rig = _Rig()..token = null;
      rig.socket.start();
      async.flushMicrotasks();
      expect(rig.renewals, 1);
      expect(rig.sentFrame(0, 0)['token'], rig.token);
    });
  });

  test('stopping closes the connection, says so and tries nothing more', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      async.flushMicrotasks();
      rig.server.last.say(_ready());
      async.flushMicrotasks();
      rig.socket.stop();
      async.flushMicrotasks();
      expect(rig.server.links[0].closedByClient, isTrue);
      expect(rig.events.last, isA<ChatDisconnected>());
      async.elapse(const Duration(minutes: 5));
      expect(rig.server.links.length, 1);
      expect(rig.socket.status, ChatSocketStatus.stopped);
      rig.socket.start();
      async.flushMicrotasks();
      expect(rig.server.links.length, 2);
    });
  });

  test('starting twice opens one connection', () {
    fakeAsync((async) {
      final rig = _Rig()..socket.start();
      rig.socket.start();
      async.flushMicrotasks();
      rig.socket.start();
      async.flushMicrotasks();
      expect(rig.server.addresses.length, 1);
    });
  });
}
