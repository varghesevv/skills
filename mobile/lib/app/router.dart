import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/user_type.dart';
import '../core/session/session_controller.dart';
import '../features/auth/auth_widgets.dart';
import '../features/auth/forgot_password_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/register_screen.dart';
import '../features/auth/welcome_screen.dart';
import '../features/home/dashboard_screen.dart';
import '../features/settings/settings_screen.dart';
import 'shell.dart';

const _signedOutPrefixes = [
  '/welcome',
  '/login',
  '/register',
  '/forgot-password',
];

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
      final signedIn = session.value != null;
      final path = state.matchedLocation;
      final onSignedOut = _signedOutPrefixes.any(path.startsWith);
      if (!signedIn) return onSignedOut ? null : '/welcome';
      return onSignedOut || path == '/splash' ? '/home' : null;
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
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/home',
                builder: (context, state) => const DashboardScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/settings',
                builder: (context, state) => const SettingsScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});

Widget _forType(GoRouterState state, Widget Function(UserType type) build) {
  final type = userTypeFromRoute(state.pathParameters['type']);
  // An unknown role in the address goes back to the start; nothing is guessed.
  return type == null ? const WelcomeScreen() : build(type);
}
