import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config_gate.dart';
import 'router.dart';
import 'theme.dart';

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
