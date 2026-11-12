import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app/destinations.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';

/// The first screen after login: who you are signed in as. Feature shortcuts are added with the
/// features of each role (phases 2 to 4).
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final me = ref.watch(sessionProvider).value;
    if (me == null) return const SizedBox.shrink();
    final shortcuts = shortcutsFor(me.userType);
    final since = DateFormat.yMMMd().format(me.createdAt.toLocal());
    Widget fact(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Semantics(
        container: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            Text(value, style: Theme.of(context).textTheme.bodyLarge),
          ],
        ),
      ),
    );
    return Scaffold(
      appBar: AppBar(title: Text(text('dashboard.title'))),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              text('dashboard.welcome', {'name': me.displayName}),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(text('dashboard.lead.${me.userType.wire}')),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      text('dashboard.account'),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    fact(text('dashboard.email'), me.email),
                    fact(text('dashboard.mobile'), me.mobileNumber),
                    fact(
                      text('dashboard.role'),
                      text('role.${me.userType.wire}'),
                    ),
                    fact(text('dashboard.since'), since),
                  ],
                ),
              ),
            ),
            if (shortcuts.isNotEmpty) ...[
              const SizedBox(height: 16),
              Semantics(
                header: true,
                child: Text(
                  text('dashboard.shortcuts'),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              for (final shortcut in shortcuts)
                Card(
                  child: ListTile(
                    leading: Icon(shortcut.icon),
                    title: Text(text(shortcut.labelKey)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.go(shortcut.location),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
