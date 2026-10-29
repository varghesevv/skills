import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/api_client.dart';
import 'auth/auth_repository.dart';
import 'auth/token_store.dart';
import 'env.dart';
import 'terminology/app_config.dart';
import 'terminology/terms.dart';

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );
});

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    dio: ref.watch(dioProvider),
    tokens: ref.watch(tokenStoreProvider),
    appVersion: Env.appVersion,
  );
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(tokenStoreProvider),
  );
});

final appConfigRepositoryProvider = Provider<AppConfigRepository>((ref) {
  return AppConfigRepository(ref.watch(apiClientProvider));
});

/// The installation's words and app versions. Screens wait for it (or show "try again")
/// before they show any role word: there is no built-in copy of the words.
final appConfigProvider = FutureProvider<AppConfig>((ref) {
  return ref.watch(appConfigRepositoryProvider).fetch();
});

/// The words, once the app config has loaded.
final termsProvider = Provider<Terms?>((ref) {
  return ref
      .watch(appConfigProvider)
      .whenOrNull(data: (config) => config.terms);
});
