import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_client.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/features/person/data/person_repository.dart';

import '../../support/fake_api.dart';
import '../../support/memory_token_store.dart';
import '../../support/test_app.dart';

void main() {
  late FakeAdapter adapter;
  late PersonRepository repository;

  setUp(() {
    adapter = FakeAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
      ..httpClientAdapter = adapter;
    repository = PersonRepository(
      ApiClient(dio: dio, tokens: MemoryTokenStore()),
    );
  });

  test('lists churches and home groups without a login', () async {
    adapter
      ..reply(
        'GET',
        '/churches',
        FakeReply(200, {
          'items': [
            {'id': 'c1', 'name': 'Grace'},
          ],
        }),
      )
      ..reply(
        'GET',
        '/churches/c1/home-groups',
        FakeReply(200, {
          'items': [
            {'id': 'g1', 'name': 'Riverside', 'leader_name': 'Lena'},
          ],
        }),
      );
    expect((await repository.churches()).single.name, 'Grace');
    expect((await repository.homeGroups('c1')).single.leaderName, 'Lena');
    expect(adapter.seen.every((r) => r.authorization == null), isTrue);
  });

  test('a link token goes in the body, never in the address', () async {
    final token = fresh('tok');
    adapter.reply(
      'POST',
      '/group-invitations/lookup',
      FakeReply(200, {
        'church_name': 'Grace',
        'home_group_name': 'Riverside',
        'leader_name': 'Lena',
      }),
    );
    final info = await repository.lookupInvitation(token);
    expect(info.homeGroupName, 'Riverside');
    final request = adapter.seen.single;
    expect(request.body, {'token': token});
    expect(request.path.contains(token), isFalse);
  });

  test('sign-up sends a group id or a token, never both', () async {
    adapter.reply('POST', '/auth/signup', FakeReply(201, {'id': 'x'}));
    await repository.signUp(
      fullName: 'N',
      email: 'n@example.test',
      mobileNumber: '+10000000000',
      password: fresh('pw'),
      requestedStatus: 'searcher',
      homeGroupId: 'g1',
    );
    await repository.signUp(
      fullName: 'N',
      email: 'n@example.test',
      mobileNumber: '+10000000000',
      password: fresh('pw'),
      requestedStatus: 'provider',
      invitationToken: 'tok',
    );
    final bodies = adapter.seen.map((r) => r.body as Map).toList();
    expect(bodies[0].containsKey('invitation_token'), isFalse);
    expect(bodies[0]['home_group_id'], 'g1');
    expect(bodies[1].containsKey('home_group_id'), isFalse);
    expect(bodies[1]['invitation_token'], 'tok');
  });

  test('an answer of the wrong shape is a bad response, not a crash', () async {
    adapter.reply('GET', '/churches', FakeReply(200, {'items': 'nope'}));
    await expectLater(repository.churches(), throwsA(isA<ApiException>()));
  });

  test('closing the account sends the password in the body', () async {
    final password = fresh('pw');
    adapter.reply('DELETE', '/me', FakeReply(204));
    await repository.closeAccount(password);
    final request = adapter.seen.single;
    expect(request.method, 'DELETE');
    expect(request.body, {'password': password});
  });

  test('a refused change is an ApiException with the server code', () async {
    adapter.reply(
      'PUT',
      '/me/application',
      FakeReply(409, apiError('not_pending')),
    );
    await expectLater(
      repository.updateApplication(requestedStatus: 'provider'),
      throwsA(isA<ApiException>().having((e) => e.code, 'code', 'not_pending')),
    );
  });

  test(
    'the person from the server is read with its group and leader',
    () async {
      adapter.reply(
        'PUT',
        '/me/application',
        FakeReply(200, personJson(vouches: 2)),
      );
      final person = await repository.updateApplication(
        requestedStatus: 'searcher',
      );
      expect(person.vouchCount, 2);
      expect(person.homeGroup?.name, 'Riverside');
      expect(person.leaderName, 'Lena Leader');
    },
  );
}
