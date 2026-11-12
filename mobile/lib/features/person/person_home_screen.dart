import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/person_me.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../core/session/session_controller.dart';
import 'applicant_home.dart';

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
      Text(text('member.soon')),
    ],
  );
}
