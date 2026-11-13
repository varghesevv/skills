import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/person_me.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../shared/widgets/message_banner.dart';
import 'vouch_share.dart';

/// For a searcher: ask to offer skills, then collect vouches like a new applicant. They stay a
/// searcher meanwhile. Shown only to a SEARCHER; everyone else has nothing to ask for here.
class ProviderUpgrade extends ConsumerStatefulWidget {
  const ProviderUpgrade({super.key, required this.person});

  final PersonMe person;

  @override
  ConsumerState<ProviderUpgrade> createState() => _ProviderUpgradeState();
}

class _ProviderUpgradeState extends ConsumerState<ProviderUpgrade> {
  bool _busy = false;
  String? _error;

  Future<void> _apply() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final updated = await ref.read(personRepositoryProvider).applyProvider();
      if (!mounted) return;
      ref.read(sessionProvider.notifier).setPerson(updated);
    } catch (error) {
      if (!mounted) return;
      final text = ref.read(appTextProvider);
      setState(
        () => _error = error is ApiException && error.code == 'not_searcher'
            ? text('upgrade.error.status')
            : text.error(error),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final person = widget.person;
    if (person.status != PersonStatus.searcher) return const SizedBox.shrink();
    final text = ref.watch(appTextProvider);
    final asked = person.requestedStatus == 'provider';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(height: 32),
        Semantics(
          header: true,
          child: Text(
            asked ? text('upgrade.waiting.title') : text('upgrade.title'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        const SizedBox(height: 8),
        if (!asked) ...[
          Text(text('upgrade.text')),
          if (_error != null) ...[
            const SizedBox(height: 8),
            MessageBanner(_error!),
          ],
          const SizedBox(height: 8),
          FilledButton(
            key: const Key('apply-provider'),
            onPressed: _busy ? null : _apply,
            child: Text(
              _busy ? text('upgrade.working') : text('upgrade.apply'),
            ),
          ),
        ] else ...[
          Text(
            person.vouchCount == 1
                ? text('upgrade.waiting.one')
                : text('upgrade.waiting', {'count': '${person.vouchCount}'}),
          ),
          const SizedBox(height: 16),
          const VouchShare(),
        ],
      ],
    );
  }
}
