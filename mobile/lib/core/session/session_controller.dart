import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/account.dart';
import '../auth/me.dart';
import '../auth/person_me.dart';
import '../auth/user_type.dart';
import '../providers.dart';

/// Who is signed in: loading at start-up, then the account or null (signed out).
class SessionController extends AsyncNotifier<Account?> {
  @override
  Future<Account?> build() async {
    // The API client signals when the server rejects the refresh token: the session is over.
    ref.listen(sessionExpiredProvider, (_, _) => expire());
    try {
      return await ref.read(authRepositoryProvider).restoreSession();
    } on Exception {
      // No connection at start-up: show the login screen; the saved session is kept for later.
      return null;
    }
  }

  /// Throws `ApiException` on a wrong password and so on; the caller shows the message.
  Future<void> login({
    required String email,
    required String password,
    required UserType type,
  }) async {
    final me = await ref
        .read(authRepositoryProvider)
        .login(email: email, password: password, type: type);
    state = AsyncData(me);
  }

  /// The one login of the church trust model. Throws `ApiException` like [login].
  Future<void> loginPerson({
    required String email,
    required String password,
  }) async {
    final person = await ref
        .read(authRepositoryProvider)
        .loginPerson(email: email, password: password);
    state = AsyncData(person);
  }

  /// A change of the person's own data (the application, for example) came back from the server.
  void setPerson(PersonMe person) => state = AsyncData(person);

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AsyncData(null);
  }

  /// The server rejected the refresh token: back to the login screen.
  void expire() => state = const AsyncData(null);
}

final sessionProvider = AsyncNotifierProvider<SessionController, Account?>(
  SessionController.new,
);

/// The signed-in older account, or null for a person of the church trust model or nobody.
final meProvider = Provider<Me?>((ref) {
  final account = ref.watch(sessionProvider).value;
  return account is Me ? account : null;
});

/// The signed-in person of the church trust model, or null.
final personProvider = Provider<PersonMe?>((ref) {
  final account = ref.watch(sessionProvider).value;
  return account is PersonMe ? account : null;
});
