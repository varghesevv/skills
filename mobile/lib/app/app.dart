import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;

import 'config_gate.dart';
import 'router.dart';
import 'theme.dart';

/// Riverpod 3 retries a failed provider on its own (up to 10 times over about 40 seconds). Here
/// that would hide errors behind a long spinner, hammer a server that is already failing and
/// ignore a 429 `Retry-After`. Failures show at once and "Try again" is the person's choice.
Duration? noAutomaticRetry(int retryCount, Object error) => null;

/// The root of the app, shared by `main` and the tests so both use the same retry policy.
Widget appRoot({List<Override> overrides = const []}) => ProviderScope(
  retry: noAutomaticRetry,
  overrides: overrides,
  child: const SkillsApp(),
);

class SkillsApp extends ConsumerWidget {
  const SkillsApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'Skills',
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      routerConfig: ref.watch(routerProvider),
      builder: (context, child) =>
          ConfigGate(child: child ?? const SizedBox.shrink()),
    );
  }
}
