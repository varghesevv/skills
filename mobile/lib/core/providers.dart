import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/api_client.dart';
import 'auth/auth_repository.dart';
import 'auth/token_store.dart';
import 'env.dart';
import 'terminology/app_config.dart';
import 'strings/app_text.dart';
import 'terminology/terms.dart';

/// Counts the times the server rejected the refresh token (the session is over). The session
/// controller listens to it and returns to the login screen.
class SessionExpiry extends Notifier<int> {
  @override
  int build() => 0;

  void signal() => state++;
}

final sessionExpiredProvider = NotifierProvider<SessionExpiry, int>(
  SessionExpiry.new,
);

/// The running app's version (`X.Y.Z`); empty in debug and test runs. Overridden in tests.
final appVersionProvider = Provider<String>((ref) => Env.appVersion);

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
    onSessionExpired: () => ref.read(sessionExpiredProvider.notifier).signal(),
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

/// Texts with the role words filled in. Only valid once the app config has loaded; the config
/// gate keeps every screen behind that.
final appTextProvider = Provider<AppText>((ref) {
  final terms = ref.watch(termsProvider);
  if (terms == null) throw StateError('Role words are not loaded yet');
  return AppText(terms);
});
