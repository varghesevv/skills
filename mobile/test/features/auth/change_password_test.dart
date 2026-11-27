import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/router.dart';
import 'package:skills_app/core/auth/person_me.dart';
import 'package:skills_app/features/person/person_router_paths.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart';

// Made-up passwords for the form: nothing here is a credential.
const _temporary = 'temporary-pass-1';
const _chosen = 'my-own-password-2';

Map<String, Object?> _mustChange({bool flag = true}) => {
  ...personJson(status: 'owner', requested: null, name: 'Ray Minister'),
  'must_change_password': flag,
};

void main() {
  group('a temporary password from the initial config', () {
    test('opens nothing but the change-password screen', () {
      final person = PersonMe.fromJson(_mustChange());
      expect(person.mustChangePassword, isTrue);
      expect(personMayVisit(person, personChangePassword), isTrue);
      for (final path in [personHome, personSearch, personAccount]) {
        expect(personMayVisit(person, path), isFalse, reason: path);
      }
      final done = PersonMe.fromJson(_mustChange(flag: false));
      expect(personMayVisit(done, personChangePassword), isFalse);
      expect(personMayVisit(done, personHome), isTrue);
    });

    test('an older server that does not send the flag means no change', () {
      expect(PersonMe.fromJson(personJson()).mustChangePassword, isFalse);
    });

    testWidgets('is replaced, and the app opens with the new tokens', (
      tester,
    ) async {
      final app = await pumpApp(
        tester,
        size: const Size(400, 1200),
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _mustChange());
          adapter
            ..reply(
              'POST',
              '/auth/change-password',
              FakeReply(200, tokens('access-new', 'refresh-new')),
            )
            ..reply('GET', '/me', FakeReply(200, _mustChange(flag: false)))
            ..reply(
              'GET',
              '/me/notifications',
              FakeReply(200, {'items': [], 'total': 0, 'unread_count': 0}),
            );
        },
      );
      expect(find.text('Choose your own password'), findsOneWidget);

      await tapKey(tester, 'change-submit');
      expect(find.text('This field is required.'), findsOneWidget);
      expect(app.adapter.count('POST', '/auth/change-password'), 0);

      await typeInto(tester, 'Temporary password', _temporary);
      await typeInto(tester, 'New password', _chosen);
      await tapKey(tester, 'change-submit');

      final sent = app.adapter.seen.lastWhere(
        (r) => r.path == '/auth/change-password',
      );
      expect(sent.body, {
        'current_password': _temporary,
        'new_password': _chosen,
      });
      expect(await app.store.readRefreshToken(), 'refresh-new');
      expect(find.text('Choose your own password'), findsNothing);
    });

    testWidgets('explains a wrong temporary password', (tester) async {
      await pumpApp(
        tester,
        size: const Size(400, 1200),
        arrange: (adapter, store) {
          signedInAsPerson(adapter, store, _mustChange());
          adapter.reply(
            'POST',
            '/auth/change-password',
            FakeReply(403, {
              'error': {
                'code': 'invalid_password',
                'message': 'The password is not correct',
                'details': {},
              },
            }),
          );
        },
      );
      await typeInto(tester, 'Temporary password', 'not-the-one-123');
      await typeInto(tester, 'New password', _chosen);
      await tapKey(tester, 'change-submit');
      expect(find.text('The password is not correct.'), findsOneWidget);
      expect(find.text('Choose your own password'), findsOneWidget);
    });
  });
}
