import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

const _churches = {
  'items': [
    {'id': 'church-1', 'name': 'Grace Church'},
    {'id': 'church-2', 'name': 'Hope Church'},
  ],
};
const _groups = {
  'items': [
    {'id': 'group-1', 'name': 'Riverside', 'leader_name': 'Lena Leader'},
    {'id': 'group-2', 'name': 'Hilltop', 'leader_name': 'Hari Host'},
  ],
};
const _otherGroups = {
  'items': [
    {'id': 'group-9', 'name': 'Harbour', 'leader_name': 'Hana Leader'},
  ],
};

void _lists(FakeAdapter adapter) => adapter
  ..reply('GET', '/churches', FakeReply(200, _churches))
  ..reply('GET', '/churches/church-1/home-groups', FakeReply(200, _groups))
  ..reply(
    'GET',
    '/churches/church-2/home-groups',
    FakeReply(200, _otherGroups),
  );

/// For small screens and large text: fields below the fold are built only when scrolled to.
Future<void> _fillDetailsScrolling(WidgetTester tester, String password) async {
  for (final (label, value) in [
    ('Full name', 'Nadia Applicant'),
    ('Email', 'nadia@example.test'),
    ('Mobile number', '+971500000002'),
    ('New password', password),
  ]) {
    final field = find.widgetWithText(TextField, label);
    await tester.scrollUntilVisible(
      field,
      100,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(field, value);
  }
}

Future<void> _fillDetails(WidgetTester tester, String password) async {
  await typeInto(tester, 'Full name', 'Nadia Applicant');
  await typeInto(tester, 'Email', 'nadia@example.test');
  await typeInto(tester, 'Mobile number', '+971 50 000 0002');
  await typeInto(tester, 'New password', password);
}

void main() {
  group('sign in', () {
    testWidgets('is offered next to joining on the welcome screen', (
      tester,
    ) async {
      await pumpApp(tester);
      expect(find.byKey(const Key('member-join')), findsOneWidget);
      expect(find.byKey(const Key('member-sign-in')), findsOneWidget);
    });

    testWidgets('sends no account type and shows the application', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter
          ..reply(
            'POST',
            '/auth/login',
            FakeReply(200, tokens(fresh('a'), fresh('r'))),
          )
          ..reply('GET', '/me', FakeReply(200, personJson())),
      );
      await tapKey(tester, 'member-sign-in');
      await typeInto(tester, 'Email', 'nadia@example.test');
      await typeInto(tester, 'Password', password);
      await tapKey(tester, 'member-login-submit');
      expect(find.text('Your application'), findsWidgets);
      final login = app.adapter.seen.firstWhere((r) => r.path == '/auth/login');
      expect(login.body, {'email': 'nadia@example.test', 'password': password});
    });

    testWidgets('a wrong password shows one message and clears the field', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/auth/login',
          FakeReply(401, apiError('invalid_credentials')),
        ),
      );
      await tapKey(tester, 'member-sign-in');
      await typeInto(tester, 'Email', 'nadia@example.test');
      await typeInto(tester, 'Password', fresh('pw'));
      await tapKey(tester, 'member-login-submit');
      expect(find.text('Invalid email or password.'), findsOneWidget);
    });

    testWidgets('validates before asking the server', (tester) async {
      final app = await pumpApp(tester);
      await tapKey(tester, 'member-sign-in');
      await tapKey(tester, 'member-login-submit');
      expect(app.adapter.count('POST', '/auth/login'), 0);
      expect(find.text('This field is required.'), findsNWidgets(2));
    });
  });

  group('sign up', () {
    testWidgets('walks through the four steps and sends one request', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          adapter.reply(
            'POST',
            '/auth/signup',
            FakeReply(201, {'id': 'x', 'status': 'pending'}),
          );
        },
      );
      await tapKey(tester, 'member-join');
      expect(find.textContaining('Step 1 of 4'), findsOneWidget);
      await _fillDetails(tester, password);
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'church-church-1');
      await tapKey(tester, 'signup-next');
      expect(find.textContaining('Led by Hari Host'), findsOneWidget);
      await tapKey(tester, 'group-group-2');
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'apply-provider');
      await tapKey(tester, 'signup-submit');

      expect(find.text('Thank you'), findsWidgets);
      expect(app.adapter.count('POST', '/auth/signup'), 1);
      final body = app.adapter.seen
          .firstWhere((r) => r.path == '/auth/signup')
          .body;
      expect(body, {
        'full_name': 'Nadia Applicant',
        'email': 'nadia@example.test',
        'mobile_number': '+971500000002',
        'password': password,
        'requested_status': 'provider',
        'home_group_id': 'group-2',
      });
    });

    testWidgets('does not go on with bad details or without a choice', (
      tester,
    ) async {
      final app = await pumpApp(tester, arrange: (a, s) => _lists(a));
      await tapKey(tester, 'member-join');
      await typeInto(tester, 'Full name', 'Nadia Applicant');
      await typeInto(tester, 'Email', 'nadia@example.test');
      await typeInto(tester, 'Mobile number', '+971500000002');
      await typeInto(tester, 'New password', 'short');
      await tapKey(tester, 'signup-next');
      expect(find.text('Use at least 10 characters.'), findsOneWidget);
      expect(find.textContaining('Step 1 of 4'), findsOneWidget);

      await typeInto(tester, 'New password', fresh('pw'));
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'signup-next'); // no church chosen
      expect(find.textContaining('Step 2 of 4'), findsOneWidget);
      expect(find.text('Choose your organisation'), findsWidgets);
      expect(app.adapter.count('POST', '/auth/signup'), 0);
    });

    testWidgets('going back keeps what was typed', (tester) async {
      await pumpApp(tester, arrange: (a, s) => _lists(a));
      await tapKey(tester, 'member-join');
      await _fillDetails(tester, fresh('pw'));
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'signup-back');
      expect(find.text('Nadia Applicant'), findsOneWidget);
      expect(find.text('nadia@example.test'), findsOneWidget);
    });

    for (final (code, message) in [
      ('account_exists', 'An account with these details already exists'),
      ('invalid_choice', 'is not available'),
      ('rate_limited', 'Too many requests'),
    ]) {
      testWidgets('shows a message for $code', (tester) async {
        await pumpApp(
          tester,
          arrange: (adapter, store) {
            _lists(adapter);
            adapter.reply(
              'POST',
              '/auth/signup',
              FakeReply(code == 'invalid_choice' ? 422 : 409, apiError(code)),
            );
          },
        );
        await tapKey(tester, 'member-join');
        await _fillDetails(tester, fresh('pw'));
        await tapKey(tester, 'signup-next');
        await tapKey(tester, 'church-church-1');
        await tapKey(tester, 'signup-next');
        await tapKey(tester, 'group-group-1');
        await tapKey(tester, 'signup-next');
        await tapKey(tester, 'signup-submit');
        expect(find.textContaining(message), findsOneWidget);
        expect(find.text('Thank you'), findsNothing);
      });
    }

    testWidgets('says when there is no church to join', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) =>
            adapter.reply('GET', '/churches', FakeReply(200, {'items': []})),
      );
      await tapKey(tester, 'member-join');
      await _fillDetails(tester, fresh('pw'));
      await tapKey(tester, 'signup-next');
      expect(
        find.text('There is no organisation to join yet.'),
        findsOneWidget,
      );
    });
  });

  group('sign up with an invitation link', () {
    final token = fresh('tok');

    testWidgets('uses the group of the link and skips two steps', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) => adapter
          ..reply(
            'POST',
            '/group-invitations/lookup',
            FakeReply(200, {
              'church_name': 'Grace Church',
              'home_group_name': 'Riverside',
              'leader_name': 'Lena Leader',
            }),
          )
          ..reply(
            'POST',
            '/auth/signup',
            FakeReply(201, {'id': 'x', 'status': 'pending'}),
          ),
      );
      // Paste the link into the sign-up screen, as a person would.
      await tapKey(tester, 'member-join');
      await tapKey(tester, 'have-link');
      await tester.enterText(
        find.byType(TextField).last,
        'https://skills.example.test/join/$token',
      );
      await tapKey(tester, 'use-link');
      expect(
        find.textContaining(
          'invited to Riverside in Grace Church, led by Lena Leader',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Step 1 of 2'), findsOneWidget);
      await _fillDetails(tester, password);
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'signup-submit');

      expect(find.text('Thank you'), findsWidgets);
      final lookup = app.adapter.seen.firstWhere(
        (r) => r.path == '/group-invitations/lookup',
      );
      expect(lookup.body, {'token': token});
      final body =
          app.adapter.seen.firstWhere((r) => r.path == '/auth/signup').body
              as Map;
      expect(body['invitation_token'], token);
      expect(body.containsKey('home_group_id'), isFalse);
      expect(app.adapter.count('GET', '/churches'), 0);
      // The token never appears in the address of a request.
      expect(app.adapter.seen.every((r) => !r.path.contains(token)), isTrue);
    });

    testWidgets('offers to choose a group when the link does not work', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => adapter.reply(
          'POST',
          '/group-invitations/lookup',
          FakeReply(404, apiError('not_found')),
        ),
      );
      await tapKey(tester, 'member-join');
      await tapKey(tester, 'have-link');
      await tester.enterText(find.byType(TextField).last, token);
      await tapKey(tester, 'use-link');
      expect(
        find.textContaining('invitation link is not valid'),
        findsOneWidget,
      );
      expect(find.text('Choose my home group'), findsOneWidget);
    });

    testWidgets('ignores a link that is too short to be one', (tester) async {
      final app = await pumpApp(tester);
      await tapKey(tester, 'member-join');
      await tapKey(tester, 'have-link');
      await tester.enterText(find.byType(TextField).last, 'abc');
      await tapKey(tester, 'use-link');
      expect(app.adapter.count('POST', '/group-invitations/lookup'), 0);
      expect(find.textContaining('Step 1 of 4'), findsOneWidget);
    });
  });

  group('large text on a small phone', () {
    testWidgets('the sign-up wizard still fits at twice the text size', (
      tester,
    ) async {
      await pumpApp(
        tester,
        textScale: 2.0,
        size: const Size(360, 640),
        arrange: (adapter, store) => _lists(adapter),
      );
      await tapKey(tester, 'member-join');
      await _fillDetailsScrolling(tester, fresh('pw'));
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'church-church-1');
      await tapKey(tester, 'signup-next');
      await tapKey(tester, 'group-group-1');
      await tapKey(tester, 'signup-next');
      await tester.scrollUntilVisible(
        find.byKey(const Key('signup-submit')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.byKey(const Key('signup-submit')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
