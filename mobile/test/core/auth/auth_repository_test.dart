import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_client.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/auth/auth_repository.dart';

import '../../support/memory_token_store.dart';

import '../../support/fake_api.dart';
import '../../support/test_app.dart' show personJson;

void main() {
  late FakeAdapter adapter;
  late MemoryTokenStore store;
  late AuthRepository auth;

  setUp(() {
    adapter = FakeAdapter();
    store = MemoryTokenStore();
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
      ..httpClientAdapter = adapter;
    auth = AuthRepository(ApiClient(dio: dio, tokens: store), store);
  });

  test(
    'login sends no account type, keeps the tokens and returns the person',
    () async {
      final password = fresh('pw');
      final access = fresh('a');
      final refresh = fresh('r');
      adapter
        ..reply('POST', '/auth/login', FakeReply(200, tokens(access, refresh)))
        ..reply('GET', '/me', FakeReply(200, personJson()));
      final person = await auth.loginPerson(
        email: 'person@example.test',
        password: password,
      );
      expect(person.id, personJson()['id']);
      expect(adapter.seen.first.body, {
        'email': 'person@example.test',
        'password': password,
      });
      expect(adapter.seen.first.authorization, isNull);
      expect(store.accessToken, access);
      expect(await store.readRefreshToken(), refresh);
    },
  );

  test(
    'a wrong password throws invalid_credentials and stores nothing',
    () async {
      adapter.reply(
        'POST',
        '/auth/login',
        FakeReply(401, apiError('invalid_credentials')),
      );
      await expectLater(
        auth.loginPerson(email: 'person@example.test', password: fresh('pw')),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'invalid_credentials',
          ),
        ),
      );
      expect(store.accessToken, isNull);
      expect(await store.readRefreshToken(), isNull);
    },
  );

  test(
    'a login answer without tokens is a bad response and stores nothing',
    () async {
      adapter.reply(
        'POST',
        '/auth/login',
        FakeReply(200, {'unexpected': true}),
      );
      await expectLater(
        auth.loginPerson(email: 'person@example.test', password: fresh('pw')),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
        ),
      );
      expect(store.accessToken, isNull);
      expect(await store.readRefreshToken(), isNull);
    },
  );

  test(
    'a login whose account cannot be loaded leaves no session behind',
    () async {
      adapter
        ..reply(
          'POST',
          '/auth/login',
          FakeReply(200, tokens(fresh('a'), fresh('r'))),
        )
        ..reply(
          'GET',
          '/me',
          FakeReply(200, {'id': 'u1', 'user_type': 'admin'}),
        );
      await expectLater(
        auth.loginPerson(email: 'person@example.test', password: fresh('pw')),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
        ),
      );
      expect(store.accessToken, isNull);
      expect(await store.readRefreshToken(), isNull);
    },
  );

  test('a server error while loading the account after login also clears the session', () async {
    adapter
      ..reply(
        'POST',
        '/auth/login',
        FakeReply(200, tokens(fresh('a'), fresh('r'))),
      )
      ..reply('GET', '/me', FakeReply(503, apiError('service_unavailable')));
    await expectLater(
      auth.loginPerson(email: 'person@example.test', password: fresh('pw')),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 503)),
    );
    expect(await store.readRefreshToken(), isNull);
  });

  test('an account of the older kind is not a person', () async {
    adapter.reply(
      'GET',
      '/me',
      FakeReply(200, {'id': 'u1', 'user_type': 'freelancer'}),
    );
    await expectLater(auth.me(), throwsA(isA<OlderAccountException>()));
  });

  test('restoreSession returns null without a saved session', () async {
    expect(await auth.restoreSession(), isNull);
    expect(adapter.seen, isEmpty);
  });

  test('restoreSession refreshes and loads the account', () async {
    await store.save(accessToken: fresh('a'), refreshToken: fresh('r'));
    final fresher = MemoryTokenStore();
    await fresher.save(accessToken: fresh('a'), refreshToken: fresh('r'));
    // Simulate an app start: the refresh token exists, the access token does not.
    final coldStart = _ColdStartStore(await store.readRefreshToken());
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
      ..httpClientAdapter = adapter;
    final repo = AuthRepository(
      ApiClient(dio: dio, tokens: coldStart),
      coldStart,
    );
    adapter
      ..reply(
        'POST',
        '/auth/refresh',
        FakeReply(200, tokens(fresh('a'), fresh('r'))),
      )
      ..reply('GET', '/me', FakeReply(200, personJson()));
    expect((await repo.restoreSession())?.id, personJson()['id']);
  });

  test('a saved session of an older account is ended, not kept', () async {
    final coldStart = _ColdStartStore('saved-refresh');
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
      ..httpClientAdapter = adapter;
    final repo = AuthRepository(
      ApiClient(dio: dio, tokens: coldStart),
      coldStart,
    );
    adapter
      ..reply(
        'POST',
        '/auth/refresh',
        FakeReply(200, tokens(fresh('a'), fresh('r'))),
      )
      ..reply(
        'GET',
        '/me',
        FakeReply(200, {'id': 'u1', 'user_type': 'workhost'}),
      )
      ..reply('POST', '/auth/logout', FakeReply(204));
    expect(await repo.restoreSession(), isNull);
    expect(await coldStart.readRefreshToken(), isNull);
    // The abandoned refresh token is revoked on the server too.
    expect(adapter.count('POST', '/auth/logout'), 1);
  });

  group('a saved session is kept when /me cannot be read, but not for an older account', () {
    Future<(AuthRepository, _ColdStartStore)> coldRepo(FakeReply me) async {
      final store = _ColdStartStore('saved-refresh');
      final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
        ..httpClientAdapter = adapter;
      adapter
        ..reply(
          'POST',
          '/auth/refresh',
          FakeReply(200, tokens(fresh('a'), fresh('r'))),
        )
        ..reply('GET', '/me', me);
      return (AuthRepository(ApiClient(dio: dio, tokens: store), store), store);
    }

    final cases = {
      'an unknown status': FakeReply(200, {
        ...personJson(),
        'status': 'archangel',
      }),
      'a page that is not JSON': FakeReply(
        200,
        '<html>sign in to the wifi</html>',
      ),
      'an answer without an account type': FakeReply(200, {'id': 'u1'}),
    };
    cases.forEach((name, reply) {
      test('$name keeps the session and asks again next time', () async {
        final (repo, store) = await coldRepo(reply);
        await expectLater(
          repo.restoreSession(),
          throwsA(
            isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
          ),
        );
        expect(await store.readRefreshToken(), isNotNull);
        expect(adapter.count('POST', '/auth/logout'), 0);
      });
    });

    test(
      'an older account at login is refused and leaves no session',
      () async {
        adapter
          ..reply(
            'POST',
            '/auth/login',
            FakeReply(200, tokens(fresh('a'), fresh('r'))),
          )
          ..reply(
            'GET',
            '/me',
            FakeReply(200, {'id': 'u1', 'user_type': 'workhost'}),
          );
        await expectLater(
          auth.loginPerson(email: 'person@example.test', password: fresh('pw')),
          throwsA(
            isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
          ),
        );
        expect(await store.readRefreshToken(), isNull);
      },
    );
  });

  test(
    'logout revokes the token and clears the store even when offline',
    () async {
      await store.save(accessToken: fresh('a'), refreshToken: fresh('r'));
      adapter.failWithNetworkError = true;
      await auth.logout();
      expect(store.accessToken, isNull);
      expect(await store.readRefreshToken(), isNull);
    },
  );

  test('logout sends the refresh token to the server', () async {
    final refresh = fresh('r');
    await store.save(accessToken: fresh('a'), refreshToken: refresh);
    adapter.reply('POST', '/auth/logout', FakeReply(204));
    await auth.logout();
    expect(adapter.seen.single.body, {'refresh_token': refresh});
  });
}

/// A store as it is right after the app starts: refresh token saved, access token not yet loaded.
class _ColdStartStore extends MemoryTokenStore {
  _ColdStartStore(String? refresh) : _refresh = refresh;

  String? _refresh;
  String? _access;

  @override
  String? get accessToken => _access;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    _access = accessToken;
    _refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }
}
