import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/features/chat/push/push_gateway.dart';

import '../../support/fake_api.dart';
import '../../support/fake_push.dart';
import '../../support/test_app.dart';

Map<String, Object?> _conversation() => {
  'id': 'c1',
  'my_side': 'starter',
  'other': {'id': 'prov-1', 'full_name': 'Anita Provider', 'closed': false},
  'last_message_preview': 'Hello',
  'last_message_at': '2026-11-16T10:00:00Z',
  'unread_count': 0,
  'muted': false,
  'blocked': false,
};

Future<TestApp> _open(
  WidgetTester tester,
  FakePushGateway gateway, {
  MemoryPushPreferences? preferences,
  void Function(FakeAdapter adapter)? arrange,
}) => pumpApp(
  tester,
  size: const Size(400, 1200),
  pushGateway: gateway,
  pushPreferences: preferences,
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
      ..reply('GET', '/chat/conversations/c1', FakeReply(200, _conversation()))
      ..reply('GET', '/chat/conversations/c1/messages', FakeReply(200, []))
      ..reply('POST', '/chat/devices', FakeReply(201, {'id': 'device-77'}))
      ..reply('DELETE', '/chat/devices/device-77', FakeReply(204))
      ..reply('POST', '/auth/logout', FakeReply(204));
    arrange?.call(adapter);
  },
);

/// The body of the call that registers an address (the field is the API's name for it).
Map<String, Object?> _registered(String address) => {
  _addressField: address,
  'platform': 'android',
};

const _addressField = 'token';

List<Object?> _registrations(TestApp app) => [
  for (final r in app.adapter.seen)
    if (r.method == 'POST' && r.path == '/chat/devices') r.body,
];

void main() {
  testWidgets('the person is not asked at launch', (tester) async {
    final gateway = FakePushGateway();
    final app = await _open(tester, gateway);
    expect(gateway.asked, 0);
    expect(_registrations(app), isEmpty);
  });

  testWidgets(
    'opening the messages asks once, and an allowed phone is registered',
    (tester) async {
      final gateway = FakePushGateway();
      final app = await _open(tester, gateway);
      await tapKey(tester, 'messages');
      expect(gateway.asked, 1);
      expect(_registrations(app), [_registered('device-address-1')]);
      // Going back and in again, or into a thread, does not ask again.
      await tester.tap(find.byKey(const Key('conversation-c1')));
      await tester.pumpAndSettle();
      expect(gateway.asked, 1);
    },
  );

  testWidgets(
    'a person who says no is not asked again and nothing is registered',
    (tester) async {
      final gateway = FakePushGateway(answer: PushPermission.denied);
      final app = await _open(tester, gateway);
      await tapKey(tester, 'messages');
      expect(gateway.asked, 1);
      expect(_registrations(app), isEmpty);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tapKey(tester, 'messages');
      expect(gateway.asked, 1);
    },
  );

  testWidgets(
    'a phone that already allowed notifications is registered at start without asking',
    (tester) async {
      final gateway = FakePushGateway(state: PushPermission.granted);
      final app = await _open(tester, gateway);
      await tester.pump();
      expect(gateway.asked, 0);
      expect(_registrations(app).length, 1);
    },
  );

  testWidgets(
    'a person asked before is not asked again after a reinstall of the state',
    (tester) async {
      final gateway = FakePushGateway();
      await _open(
        tester,
        gateway,
        preferences: MemoryPushPreferences(wasAsked: true),
      );
      await tapKey(tester, 'messages');
      expect(gateway.asked, 0);
    },
  );

  testWidgets('a new address is registered, the same one is not sent twice', (
    tester,
  ) async {
    final gateway = FakePushGateway(state: PushPermission.granted);
    final app = await _open(tester, gateway);
    await tester.pump();
    gateway.address = 'device-address-2';
    gateway.refreshed.add('device-address-2');
    await tester.pumpAndSettle();
    gateway.refreshed.add('device-address-2');
    await tester.pumpAndSettle();
    expect(_registrations(app), [
      _registered('device-address-1'),
      _registered('device-address-2'),
    ]);
  });

  testWidgets(
    'a registration that fails is tried again with the next address',
    (tester) async {
      final gateway = FakePushGateway(state: PushPermission.granted);
      final app = await _open(
        tester,
        gateway,
        arrange: (adapter) => adapter.setReply(
          'POST',
          '/chat/devices',
          FakeReply(500, apiError('server_error')),
        ),
      );
      await tester.pump();
      expect(find.textContaining('went wrong'), findsNothing);
      app.adapter.setReply(
        'POST',
        '/chat/devices',
        FakeReply(201, {'id': 'device-77'}),
      );
      gateway.refreshed.add('device-address-1');
      await tester.pumpAndSettle();
      expect(_registrations(app).length, 2);
    },
  );

  testWidgets(
    'an address renewed while one is being registered still ends up registered',
    (tester) async {
      final gateway = FakePushGateway(state: PushPermission.granted);
      final gate = Completer<void>();
      final app = await _open(
        tester,
        gateway,
        arrange: (adapter) => adapter.setReply(
          'POST',
          '/chat/devices',
          FakeReply(201, {'id': 'device-77'}, const {}, gate.future),
        ),
      );
      await tester.pump(); // the first address is on its way and held
      gateway.address = 'device-address-2';
      gateway.refreshed.add('device-address-2');
      await tester.pump();
      gate.complete();
      await tester.pumpAndSettle();
      expect(_registrations(app), [
        _registered('device-address-1'),
        _registered('device-address-2'),
      ]);
    },
  );

  testWidgets('logging out forgets this phone first', (tester) async {
    final gateway = FakePushGateway(state: PushPermission.granted);
    final app = await _open(tester, gateway);
    await tester.pump();
    await tapKey(tester, 'log-out');
    await tester.pumpAndSettle();
    final paths = [for (final r in app.adapter.seen) '${r.method} ${r.path}'];
    final forget = paths.indexOf('DELETE /chat/devices/device-77');
    final logout = paths.indexOf('POST /auth/logout');
    expect(forget, greaterThanOrEqualTo(0));
    expect(logout, greaterThan(forget));
  });

  testWidgets('logging out without a registered phone sends no delete', (
    tester,
  ) async {
    final gateway = FakePushGateway();
    final app = await _open(tester, gateway);
    await tapKey(tester, 'log-out');
    await tester.pumpAndSettle();
    expect(app.adapter.seen.where((r) => r.method == 'DELETE'), isEmpty);
  });

  testWidgets('tapping a notification opens that conversation', (tester) async {
    final gateway = FakePushGateway(state: PushPermission.granted);
    await _open(tester, gateway);
    await tester.pump();
    gateway.opened.add('c1');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('message-input')), findsOneWidget);
    expect(find.text('Anita Provider'), findsWidgets);
  });

  testWidgets('an app started by a notification opens that conversation', (
    tester,
  ) async {
    final gateway = FakePushGateway(
      state: PushPermission.granted,
      launch: 'c1',
    );
    await _open(tester, gateway);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('message-input')), findsOneWidget);
  });

  testWidgets('without a push service the messages work and nothing is asked', (
    tester,
  ) async {
    final app = await pumpApp(
      tester,
      arrange: (adapter, store) {
        signedInAsPerson(
          adapter,
          store,
          personJson(status: 'searcher', requested: null),
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
              'items': [],
              'total': 0,
              'page': 1,
              'page_size': 50,
            }),
          );
      },
    );
    await tapKey(tester, 'messages');
    expect(find.textContaining('no messages yet'), findsOneWidget);
    expect(_registrations(app), isEmpty);
  });
}
