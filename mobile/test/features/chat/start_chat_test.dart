import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _id = 'prov-1';

Map<String, Object?> _provider() => {
  'id': _id,
  'full_name': 'Anita Provider',
  'whatsapp_availability': true,
  'nationality': 'Examplean',
  'primary_language': 'English',
  'rate_per_hour': null,
  'rate_currency': null,
  'is_rate_negotiable': false,
  'labels': <Object?>[],
  'average_rating': null,
  'rating_count': 0,
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'unavailable': <Object?>[],
  'my_rating': null,
};

Map<String, Object?> _row() => {
  'id': _id,
  'full_name': 'Anita Provider',
  'church': {'id': 'church-1', 'name': 'Grace Church'},
  'home_group': {'id': 'group-1', 'name': 'Riverside'},
  'nationality': 'Examplean',
  'primary_language': 'English',
  'whatsapp_availability': true,
  'rate_per_hour': null,
  'rate_currency': null,
  'is_rate_negotiable': false,
  'average_rating': null,
  'rating_count': 0,
  'skills': <Object?>[],
  'languages': <Object?>[],
  'timings': <Object?>[],
  'nativity': <Object?>[],
};

Map<String, Object?> _conversation() => {
  'id': 'c9',
  'my_side': 'starter',
  'other': {'id': _id, 'full_name': 'Anita Provider', 'closed': false},
  'last_message_preview': null,
  'last_message_at': null,
  'unread_count': 0,
  'muted': false,
  'blocked': false,
};

Future<TestApp> _open(
  WidgetTester tester, {
  String status = 'searcher',
  String personId = 'p1',
  void Function(FakeAdapter adapter)? arrange,
}) async {
  final app = await pumpApp(
    tester,
    size: const Size(400, 3000),
    arrange: (adapter, store) {
      signedInAsPerson(
        adapter,
        store,
        personJson(status: status, requested: null, id: personId),
      );
      adapter
        ..reply(
          'GET',
          '/me/notifications',
          FakeReply(200, {'items': [], 'total': 0, 'unread_count': 0}),
        )
        ..reply('GET', '/chat/unread', FakeReply(200, {'total': 0}))
        ..reply('GET', '/labels', FakeReply(200, <Object?>[]))
        ..reply('GET', '/churches', FakeReply(200, {'items': <Object?>[]}))
        ..reply(
          'GET',
          '/search/freelancers',
          FakeReply(200, {
            'items': [_row()],
            'total': 1,
            'page': 1,
            'page_size': 12,
          }),
        )
        ..reply('GET', '/freelancers/$_id', FakeReply(200, _provider()))
        ..reply(
          'GET',
          '/freelancers/$_id/ratings',
          FakeReply(200, {'items': [], 'total': 0, 'page': 1, 'page_size': 10}),
        )
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
          '/chat/conversations/c9',
          FakeReply(200, _conversation()),
        )
        ..reply('GET', '/chat/conversations/c9/messages', FakeReply(200, []));
      arrange?.call(adapter);
    },
  );
  await tapKey(tester, 'provider-search');
  await tester.tap(find.text('Anita Provider'));
  await tester.pumpAndSettle();
  return app;
}

void main() {
  testWidgets('Message opens the conversation with this provider', (
    tester,
  ) async {
    final app = await _open(
      tester,
      arrange: (adapter) => adapter.reply(
        'POST',
        '/chat/conversations',
        FakeReply(201, _conversation()),
      ),
    );
    await tapKey(tester, 'message-provider');
    final post = app.adapter.seen.singleWhere(
      (r) => r.method == 'POST' && r.path == '/chat/conversations',
    );
    expect(post.body, {'provider_id': _id});
    expect(find.byKey(const Key('message-input')), findsOneWidget);
  });

  testWidgets('a refused start shows the reason and stays on the page', (
    tester,
  ) async {
    await _open(
      tester,
      arrange: (adapter) => adapter.reply(
        'POST',
        '/chat/conversations',
        FakeReply(403, apiError('chat_blocked')),
      ),
    );
    await tapKey(tester, 'message-provider');
    expect(find.text('You cannot write to this person.'), findsOneWidget);
    expect(find.byKey(const Key('message-input')), findsNothing);
  });

  testWidgets('a provider looking at their own page has no Message button', (
    tester,
  ) async {
    await _open(tester, status: 'provider', personId: _id);
    expect(find.byKey(const Key('message-provider')), findsNothing);
  });
}
