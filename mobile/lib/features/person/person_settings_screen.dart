import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/session/session_controller.dart';

/// Version, a hint when a newer version exists, the privacy statement and log out. Leaving the
/// community (closing the account) stays on the home page, where every status has it.
class PersonSettingsScreen extends ConsumerStatefulWidget {
  const PersonSettingsScreen({super.key});

  @override
  ConsumerState<PersonSettingsScreen> createState() =>
      _PersonSettingsScreenState();
}

class _PersonSettingsScreenState extends ConsumerState<PersonSettingsScreen> {
  String? _error;

  Future<void> _openPrivacy(String url) async {
    var opened = false;
    try {
      opened = await ref.read(webLauncherProvider)(Uri.parse(url));
    } catch (_) {
      // Treated like "nothing could open it".
    }
    if (!mounted) return;
    setState(
      () => _error = opened
          ? null
          : ref.read(appTextProvider)('settings.privacyFailed'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final version = ref.watch(appVersionProvider);
    final privacy = ref.watch(privacyUrlProvider);
    final config = ref.watch(appConfigProvider).value;
    final newer =
        config != null && version.isNotEmpty && config.updateAvailable(version);
    return Scaffold(
      appBar: AppBar(title: Text(text('settings.title'))),
      body: SafeArea(
        child: ListView(
          children: [
            ListTile(
              title: Text(text('settings.version')),
              subtitle: Text(version.isEmpty ? 'dev' : version),
            ),
            if (newer)
              ListTile(
                key: const Key('update-hint'),
                leading: const Icon(Icons.system_update),
                title: Text(text('settings.updateAvailable')),
                subtitle: Text(text('settings.updateHint')),
              ),
            if (privacy.isNotEmpty)
              ListTile(
                key: const Key('privacy'),
                leading: const Icon(Icons.privacy_tip_outlined),
                title: Text(text('settings.privacy')),
                trailing: const Icon(Icons.open_in_new),
                onTap: () => _openPrivacy(privacy),
              ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ListTile(
              key: const Key('settings-log-out'),
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
