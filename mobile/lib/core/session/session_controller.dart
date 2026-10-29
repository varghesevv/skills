import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/me.dart';
import '../auth/user_type.dart';
import '../providers.dart';

/// Who is signed in: loading at start-up, then the account or null (signed out).
class SessionController extends AsyncNotifier<Me?> {
  @override
  Future<Me?> build() async {
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

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AsyncData(null);
  }

  /// The server rejected the refresh token: back to the login screen.
  void expire() => state = const AsyncData(null);
}

final sessionProvider = AsyncNotifierProvider<SessionController, Me?>(
  SessionController.new,
);
