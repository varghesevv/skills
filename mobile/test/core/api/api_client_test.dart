import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_client.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/auth/token_store.dart';

import '../../support/fake_api.dart';

void main() {
  late FakeAdapter adapter;
  late MemoryTokenStore store;
  late int expiredCalls;
  late ApiClient client;
  late String access;
  late String refresh;

  setUp(() async {
    adapter = FakeAdapter();
    store = MemoryTokenStore();
    expiredCalls = 0;
    access = fresh('a');
    refresh = fresh('r');
    await store.save(accessToken: access, refreshToken: refresh);
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
      ..httpClientAdapter = adapter;
    client = ApiClient(
      dio: dio,
      tokens: store,
      onSessionExpired: () => expiredCalls++,
      appVersion: '1.2.3',
    );
  });

  test('sends the bearer token and the app headers', () async {
    adapter.reply('GET', '/me', FakeReply(200, {'ok': true}));
    await client.get('/me');
    final request = adapter.seen.single;
    expect(request.authorization, 'Bearer $access');
    expect(request.headers['X-App-Platform'], 'android');
    expect(request.headers['X-App-Version'], '1.2.3');
  });

  test('sends no token on public requests', () async {
    adapter.reply('GET', '/app/config', FakeReply(200, {}));
    await client.get('/app/config', auth: false);
    expect(adapter.seen.single.authorization, isNull);
  });

  test('returns null for 204', () async {
    adapter.reply('DELETE', '/x', FakeReply(204));
    expect(await client.delete('/x'), isNull);
  });

  test(
    'refreshes once on 401 and repeats the request with the new token',
    () async {
      final newAccess = fresh('a');
      final newRefresh = fresh('r');
      adapter
        ..reply('GET', '/me', FakeReply(401, apiError('unauthorized')))
        ..reply('GET', '/me', FakeReply(200, {'id': '1'}))
        ..reply(
          'POST',
          '/auth/refresh',
          FakeReply(200, tokens(newAccess, newRefresh)),
        );
      final data = await client.get('/me') as Map;
      expect(data['id'], '1');
      expect(adapter.seen.last.authorization, 'Bearer $newAccess');
      expect(await store.readRefreshToken(), newRefresh);
      expect(adapter.seen.firstWhere((r) => r.path == '/auth/refresh').body, {
        'refresh_token': refresh,
      });
    },
  );

  test('concurrent 401s share one refresh request', () async {
    final gate = Completer<void>();
    adapter
      ..reply('GET', '/a', FakeReply(401, apiError('unauthorized')))
      ..reply('GET', '/a', FakeReply(200, {}))
      ..reply('GET', '/b', FakeReply(401, apiError('unauthorized')))
      ..reply('GET', '/b', FakeReply(200, {}))
      ..reply(
        'POST',
        '/auth/refresh',
        FakeReply(200, tokens(fresh('a'), fresh('r')), const {}, gate.future),
      );
    final both = Future.wait([client.get('/a'), client.get('/b')]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    gate.complete();
    await both;
    expect(adapter.count('POST', '/auth/refresh'), 1);
  });

  test('a rejected refresh token is forgotten and the session ends', () async {
    adapter
      ..reply('GET', '/me', FakeReply(401, apiError('unauthorized')))
      ..reply(
        'POST',
        '/auth/refresh',
        FakeReply(401, apiError('invalid_token')),
      );
    await expectLater(
      client.get('/me'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
    );
    expect(await store.readRefreshToken(), isNull);
    expect(expiredCalls, 1);
  });

  test('many requests that fail together end the session once', () async {
    adapter
      ..reply('GET', '/a', FakeReply(401, apiError('unauthorized')))
      ..reply('GET', '/b', FakeReply(401, apiError('unauthorized')))
      ..reply('GET', '/c', FakeReply(401, apiError('unauthorized')))
      ..reply(
        'POST',
        '/auth/refresh',
        FakeReply(401, apiError('invalid_token')),
      );
    final results = await Future.wait([
      client.get('/a').then((_) => 'ok', onError: (_) => 'failed'),
      client.get('/b').then((_) => 'ok', onError: (_) => 'failed'),
      client.get('/c').then((_) => 'ok', onError: (_) => 'failed'),
    ]);
    expect(results, ['failed', 'failed', 'failed']);
    expect(adapter.count('POST', '/auth/refresh'), 1);
    expect(expiredCalls, 1);
  });

  test(
    'a temporary refresh failure keeps the token and does not end the session',
    () async {
      adapter
        ..reply('GET', '/me', FakeReply(401, apiError('unauthorized')))
        ..reply(
          'POST',
          '/auth/refresh',
          FakeReply(503, apiError('service_unavailable')),
        );
      await expectLater(client.get('/me'), throwsA(isA<ApiException>()));
      expect(await store.readRefreshToken(), refresh);
      expect(expiredCalls, 0);
    },
  );

  test('maps the error envelope and Retry-After', () async {
    adapter.reply(
      'POST',
      '/freelancers/1/reveal-mobile',
      FakeReply(429, apiError('reveal_limit_reached', 'too many'), const {
        'retry-after': ['120'],
      }),
    );
    await expectLater(
      client.post('/freelancers/1/reveal-mobile', body: {}),
      throwsA(
        isA<ApiException>()
            .having((e) => e.status, 'status', 429)
            .having((e) => e.code, 'code', 'reveal_limit_reached')
            .having((e) => e.retryAfterSeconds, 'retry', 120),
      ),
    );
  });

  test('a non-JSON error body gives a generic error', () async {
    adapter.reply('GET', '/x', FakeReply(502));
    await expectLater(
      client.get('/x'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'error')
            .having((e) => e.status, 'status', 502),
      ),
    );
  });

  test('no connection becomes network_error', () async {
    adapter.failWithNetworkError = true;
    await expectLater(
      client.get('/me'),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'network_error'),
      ),
    );
  });
}
