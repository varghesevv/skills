import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/env.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';

/// Version, log out. Privacy link and account deletion are added in phase 4.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('settings.title'))),
      body: SafeArea(
        child: ListView(
          children: [
            ListTile(
              title: Text(text('settings.version')),
              subtitle: Text(Env.appVersion.isEmpty ? 'dev' : Env.appVersion),
            ),
            ListTile(
              key: const Key('log-out'),
              leading: const Icon(Icons.logout),
              title: Text(text('nav.logOut')),
              subtitle: Text(text('settings.logOutHint')),
              onTap: () => ref.read(sessionProvider.notifier).logout(),
            ),
          ],
        ),
      ),
    );
  }
}
