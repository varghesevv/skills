import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

/// Placeholder start screen. Phase 1 replaces it with the login flow and the bottom-navigation
/// shell (`StatefulShellRoute`). It shows no role words: those come from `GET /app/config`.
class StartScreen extends StatelessWidget {
  const StartScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Skills')),
      body: const Center(child: Text('Starting')),
    );
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    routes: [
      GoRoute(path: '/', builder: (context, state) => const StartScreen()),
    ],
  );
});
