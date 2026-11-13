import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/person_me.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../core/session/session_controller.dart';
import 'applicant_home.dart';
import 'person_providers.dart';
import 'person_router_paths.dart';
import 'vouch_paste_dialog.dart';

/// What a person sees after signing in depends on their status, read from the server.
class PersonHomeScreen extends ConsumerWidget {
  const PersonHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final person = ref.watch(personProvider);
    final text = ref.watch(appTextProvider);
    if (person == null) return const SizedBox.shrink();
    final (title, body) = switch (person.status) {
      PersonStatus.pending => (
        text('applicant.title'),
        ApplicantHome(person: person),
      ),
      PersonStatus.revoked => (text('revoked.title'), _Revoked(text: text)),
      _ => (text('nav.home'), _Member(person: person, text: text)),
    };
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          if (person.status != PersonStatus.revoked) const _Bell(),
          IconButton(
            key: const Key('log-out'),
            tooltip: text('nav.logOut'),
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(sessionProvider.notifier).logout(),
          ),
        ],
      ),
      body: SafeArea(child: body),
    );
  }
}

/// The bell in the top bar: a count of what is new, asked for again every minute while open.
class _Bell extends ConsumerWidget {
  const _Bell();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final unread = ref.watch(notificationsProvider).value?.unreadCount ?? 0;
    return IconButton(
      key: const Key('notifications'),
      tooltip: unread > 0
          ? text('notifications.unreadCount', {'count': '$unread'})
          : text('notifications.title'),
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text('$unread'),
        child: const Icon(Icons.notifications_outlined),
      ),
      onPressed: () => context.push(personNotifications),
    );
  }
}

class _Revoked extends StatelessWidget {
  const _Revoked({required this.text});

  final AppText text;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        text('revoked.title'),
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const SizedBox(height: 8),
      Text(text('revoked.text')),
    ],
  );
}

/// Admitted people: the screens for each status arrive in later steps of the roadmap.
class _Member extends StatelessWidget {
  const _Member({required this.person, required this.text});

  final PersonMe person;
  final AppText text;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        text('member.welcome', {'name': person.fullName}),
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const SizedBox(height: 8),
      Text(
        text('member.yourStatus', {
          'status': text('status.${person.status.name}'),
        }),
      ),
      Text([person.church.name, ?person.homeGroup?.name].join(', ')),
      const SizedBox(height: 8),
      ListTile(
        key: const Key('vouch-for-someone'),
        contentPadding: EdgeInsets.zero,
        title: Text(text('vouch.paste.open')),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => askForVouchLink(context),
      ),
      ListTile(
        key: const Key('vouches-given'),
        contentPadding: EdgeInsets.zero,
        title: Text(text('vouch.given.link')),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push(personVouches),
      ),
      const SizedBox(height: 8),
      Text(text('member.soon')),
    ],
  );
}
