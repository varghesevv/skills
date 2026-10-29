import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/auth/token_store.dart';
import 'package:skills_app/core/providers.dart';

import '../support/fake_api.dart';

void main() {
  test(
    'a rejected refresh token signals the session expiry provider once',
    () async {
      final adapter = FakeAdapter();
      final store = MemoryTokenStore();
      await store.save(accessToken: fresh('a'), refreshToken: fresh('r'));
      final container = ProviderContainer(
        overrides: [
          dioProvider.overrideWithValue(
            Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
              ..httpClientAdapter = adapter,
          ),
          tokenStoreProvider.overrideWithValue(store),
        ],
      );
      addTearDown(container.dispose);
      adapter
        ..reply('GET', '/me', FakeReply(401, apiError('unauthorized')))
        ..reply(
          'POST',
          '/auth/refresh',
          FakeReply(401, apiError('invalid_token')),
        );
      expect(container.read(sessionExpiredProvider), 0);
      await expectLater(
        container.read(apiClientProvider).get('/me'),
        throwsA(isA<ApiException>()),
      );
      expect(container.read(sessionExpiredProvider), 1);
    },
  );

  test('an app config of the wrong shape is a bad response', () async {
    final adapter = FakeAdapter()
      ..reply('GET', '/app/config', FakeReply(200, {'terminology': 'oops'}));
    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(
          Dio(BaseOptions(baseUrl: 'https://api.test/api/v1'))
            ..httpClientAdapter = adapter,
        ),
      ],
    );
    addTearDown(container.dispose);
    await expectLater(
      container.read(appConfigRepositoryProvider).fetch(),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
      ),
    );
  });
}
