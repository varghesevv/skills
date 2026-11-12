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

void _lists(FakeAdapter adapter) => adapter
  ..reply('GET', '/churches', FakeReply(200, _churches))
  ..reply('GET', '/churches/church-1/home-groups', FakeReply(200, _groups))
  ..reply(
    'GET',
    '/churches/church-2/home-groups',
    FakeReply(200, {
      'items': [
        {'id': 'group-9', 'name': 'Harbour', 'leader_name': 'Hana Leader'},
      ],
    }),
  );

void main() {
  group('the home of a person by status', () {
    testWidgets('shows an applicant where they applied and the vouches', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store, personJson(vouches: 1));
        },
      );
      expect(find.text('Grace Church'), findsWidgets);
      expect(find.text('Riverside'), findsWidgets);
      expect(find.text('Lena Leader'), findsOneWidget);
      expect(find.text('1 vouch'), findsOneWidget);
    });

    testWidgets('shows a revoked person that they have no access', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => signedInAsPerson(
          adapter,
          store,
          personJson(status: 'revoked', group: null, leader: null),
        ),
      );
      expect(find.text('No access'), findsWidgets);
      expect(find.byKey(const Key('leave-open')), findsNothing);
    });

    testWidgets('welcomes an admitted person with their status', (
      tester,
    ) async {
      await pumpApp(
        tester,
        words: churchWords,
        arrange: (adapter, store) => signedInAsPerson(
          adapter,
          store,
          personJson(status: 'provider', name: 'Pia Provider'),
        ),
      );
      expect(find.text('Welcome, Pia Provider'), findsOneWidget);
      expect(find.text('Your status: Provider'), findsOneWidget);
    });

    testWidgets('an older account never sees the person home', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) => signedInAs(adapter, store, 'freelancer'),
      );
      expect(find.text('Welcome, Pat Example'), findsOneWidget);
      expect(find.byKey(const Key('leave-open')), findsNothing);
    });

    testWidgets('signing out returns to the welcome screen', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply('POST', '/auth/logout', FakeReply(204));
        },
      );
      await tapKey(tester, 'log-out');
      expect(find.byKey(const Key('member-join')), findsOneWidget);
    });
  });

  group('change of choice', () {
    testWidgets('moves an applicant to another group', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply(
            'PUT',
            '/me/application',
            FakeReply(
              200,
              personJson(
                group: {'id': 'group-2', 'name': 'Hilltop'},
                leader: 'Hari Host',
              ),
            ),
          );
        },
      );
      await tester.ensureVisible(find.byKey(const Key('change-church')));
      await tester.tap(find.byKey(const Key('change-group-church-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('Hilltop').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'change-save');
      expect(find.text('Your choice was saved.'), findsOneWidget);
      final put = app.adapter.seen.firstWhere((r) => r.method == 'PUT');
      expect(put.body, {
        'home_group_id': 'group-2',
        'requested_status': 'searcher',
      });
      await tester.drag(find.byType(ListView), const Offset(0, 1500));
      await tester.pumpAndSettle();
      expect(find.text('Hari Host'), findsOneWidget);
    });

    testWidgets('changes only what they apply for', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply(
            'PUT',
            '/me/application',
            FakeReply(200, personJson(requested: 'provider')),
          );
        },
      );
      final save = find.byKey(const Key('change-save'));
      await tester.ensureVisible(save);
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      await tapKey(tester, 'change-apply-provider');
      await tapKey(tester, 'change-save');
      expect(app.adapter.seen.firstWhere((r) => r.method == 'PUT').body, {
        'requested_status': 'provider',
      });
    });

    testWidgets('says when the application was decided in the meantime', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply(
            'PUT',
            '/me/application',
            FakeReply(409, apiError('not_pending')),
          );
        },
      );
      await tapKey(tester, 'change-apply-provider');
      await tapKey(tester, 'change-save');
      expect(
        find.text('Your application has already been decided.'),
        findsOneWidget,
      );
    });

    testWidgets('says so when the churches cannot be loaded', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          adapter
            ..reply(
              'GET',
              '/churches',
              FakeReply(503, apiError('service_unavailable')),
            )
            ..reply(
              'GET',
              '/churches/church-1/home-groups',
              FakeReply(200, _groups),
            );
          signedInAsPerson(adapter, store);
        },
      );
      await tester.ensureVisible(find.byKey(const Key('change-church')));
      expect(find.textContaining('temporarily unavailable'), findsOneWidget);
      final save = find.byKey(const Key('change-save'));
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
    });
  });

  group('leaving', () {
    testWidgets('closes the account after the password, then signs out', (
      tester,
    ) async {
      final password = fresh('pw');
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter
            ..reply('DELETE', '/me', FakeReply(204))
            ..reply('POST', '/auth/logout', FakeReply(204));
        },
      );
      expect(find.byKey(const Key('leave-submit')), findsNothing);
      await tapKey(tester, 'leave-open');
      await typeInto(tester, 'Your password, to confirm', password);
      await tapKey(tester, 'leave-submit');
      final delete = app.adapter.seen.firstWhere((r) => r.method == 'DELETE');
      expect(delete.path, '/me');
      expect(delete.body, {'password': password});
      expect(find.byKey(const Key('member-join')), findsOneWidget);
      expect(await app.store.readRefreshToken(), isNull);
    });

    testWidgets('stays signed in and says so when the password is wrong', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
          adapter.reply(
            'DELETE',
            '/me',
            FakeReply(403, apiError('invalid_password')),
          );
        },
      );
      await tapKey(tester, 'leave-open');
      await typeInto(tester, 'Your password, to confirm', fresh('pw'));
      await tapKey(tester, 'leave-submit');
      expect(find.text('The password is not correct.'), findsOneWidget);
      expect(find.byKey(const Key('leave-open')), findsNothing);
      expect(find.byKey(const Key('leave-submit')), findsOneWidget);
    });

    testWidgets('does not call the server without a password', (tester) async {
      final app = await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
        },
      );
      await tapKey(tester, 'leave-open');
      await tapKey(tester, 'leave-submit');
      expect(app.adapter.seen.where((r) => r.method == 'DELETE'), isEmpty);
    });

    testWidgets('moves focus to the confirmation and back when cancelled', (
      tester,
    ) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
        },
      );
      await tapKey(tester, 'leave-open');
      await tester.pumpAndSettle();
      final confirmation = find.ancestor(
        of: find.text('Your password, to confirm'),
        matching: find.byType(Focus),
      );
      expect(
        Focus.of(tester.element(find.text('Your password, to confirm')))
                .hasFocus ||
            confirmation.evaluate().isNotEmpty,
        isTrue,
      );
      await tapKey(tester, 'leave-cancel');
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('leave-open')), findsOneWidget);
      final trigger = tester.widget<OutlinedButton>(
        find.byKey(const Key('leave-open')),
      );
      expect(trigger.focusNode?.hasFocus, isTrue);
    });
  });

  group('large text on a small phone', () {
    testWidgets('the application screen and the leave form still fit', (
      tester,
    ) async {
      await pumpApp(
        tester,
        textScale: 2.0,
        size: const Size(360, 640),
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
        },
      );
      await tapKey(tester, 'leave-open');
      expect(find.byKey(const Key('leave-submit')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('every button is at least 48 by 48', (tester) async {
      await pumpApp(
        tester,
        arrange: (adapter, store) {
          _lists(adapter);
          signedInAsPerson(adapter, store);
        },
      );
      await tester.pumpAndSettle();
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    });
  });
}
