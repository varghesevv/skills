import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/me.dart';
import '../core/auth/person_me.dart';
import '../core/auth/user_type.dart';
import '../core/session/session_controller.dart';
import '../features/auth/auth_widgets.dart';
import '../features/auth/forgot_password_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/register_screen.dart';
import '../features/auth/welcome_screen.dart';
import '../features/person/person_home_screen.dart';
import '../features/person/person_sign_in_screen.dart';
import '../features/person/sign_up_screen.dart';
import 'destinations.dart';
import 'shell.dart';

const _signedOutPrefixes = [
  '/welcome',
  '/login',
  '/register',
  '/forgot-password',
  '/sign-in',
  '/sign-up',
  '/join',
];

/// The home of a person of the church trust model. Until the older accounts go (roadmap S5) the
/// person screens have their own addresses next to the older ones.
const personHome = '/member';

/// Tells the router to re-run its redirect when the session changes.
class _SessionListenable extends ChangeNotifier {
  _SessionListenable(Ref ref) {
    ref.listen(sessionProvider, (_, _) => notifyListeners());
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final listenable = _SessionListenable(ref);
  ref.onDispose(listenable.dispose);

  return GoRouter(
    initialLocation: '/home',
    refreshListenable: listenable,
    redirect: (context, state) {
      final session = ref.read(sessionProvider);
      if (session.isLoading) return '/splash';
      final account = session.value;
      final path = state.matchedLocation;
      final onSignedOut = _signedOutPrefixes.any(path.startsWith);
      if (account == null) return onSignedOut ? null : '/welcome';
      if (account is PersonMe) {
        // A person lives below /member; the older accounts' pages are never shown to them.
        return path == personHome ? null : personHome;
      }
      final me = account as Me;
      if (path == personHome) return '/${me.userType.wire}/home';
      final home = '/${me.userType.wire}/home';
      if (onSignedOut || path == '/splash' || path == '/home') return home;
      // Each role lives below its own prefix; another role's pages are never shown.
      for (final type in UserType.values) {
        if (path.startsWith('/${type.wire}/') && type != me.userType) {
          return home;
        }
      }
      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        builder: (context, state) =>
            const Scaffold(body: Center(child: CircularProgressIndicator())),
      ),
      GoRoute(
        path: '/welcome',
        builder: (context, state) => const WelcomeScreen(),
      ),
      GoRoute(
        path: '/sign-in',
        builder: (context, state) => const PersonSignInScreen(),
      ),
      GoRoute(
        path: '/sign-up',
        builder: (context, state) => const SignUpScreen(),
      ),
      GoRoute(
        path: '/join/:token',
        builder: (context, state) =>
            SignUpScreen(invitationToken: state.pathParameters['token']),
      ),
      GoRoute(
        path: '/forgot-password',
        builder: (context, state) => const ForgotPasswordScreen(),
      ),
      GoRoute(
        path: personHome,
        builder: (context, state) => const PersonHomeScreen(),
      ),
      GoRoute(
        path: '/login/:type',
        builder: (context, state) =>
            _forType(state, (type) => LoginScreen(type: type)),
      ),
      GoRoute(
        path: '/register/:type',
        builder: (context, state) =>
            _forType(state, (type) => RegisterScreen(type: type)),
      ),
      GoRoute(
        path: '/forgot-password/:type',
        builder: (context, state) =>
            _forType(state, (type) => ForgotPasswordScreen(type: type)),
      ),
      for (final type in UserType.values) _shellFor(type),
    ],
  );
});

StatefulShellRoute _shellFor(UserType type) {
  final destinations = destinationsFor(type);
  return StatefulShellRoute.indexedStack(
    builder: (context, state, shell) =>
        AppShell(navigationShell: shell, destinations: destinations),
    branches: [
      for (final destination in destinations)
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/${type.wire}/${destination.path}',
              builder: (context, state) => destination.builder(),
              routes: destination.routes,
            ),
          ],
        ),
    ],
  );
}

Widget _forType(GoRouterState state, Widget Function(UserType type) build) {
  final type = userTypeFromRoute(state.pathParameters['type']);
  // An unknown role in the address goes back to the start; nothing is guessed.
  return type == null ? const WelcomeScreen() : build(type);
}
