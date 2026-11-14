import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/leader_models.dart';
import 'leader_problem.dart';

/// What happened to the person: they were declined, or admitted (with the status the server
/// gave).
sealed class Outcome {
  const Outcome();
}

class Declined extends Outcome {
  const Declined();
}

/// A revocation, a reinstatement or a re-confirmation: what the server's answer changed.
class StatusChanged extends Outcome {
  const StatusChanged({
    required this.status,
    required this.homeGroup,
    required this.flagged,
    required this.entry,
  });

  final String status;
  final IdName? homeGroup;
  final bool flagged;

  /// The line this change adds to the history, made by the person who did it.
  final HistoryEntry entry;
}

class Admitted extends Outcome {
  const Admitted(this.result);

  final AdmitResult result;
}

/// Admit as a searcher or a provider, or decline (which asks first, because it cannot be undone).
/// [canAdmitAsProvider] only switches the provider button off; the server decides.
class AdmitControls extends ConsumerStatefulWidget {
  const AdmitControls({
    super.key,
    required this.id,
    required this.name,
    required this.canAdmitAsProvider,
    required this.onDone,
    this.upgrade = false,
  });

  final String id;
  final String name;
  final bool canAdmitAsProvider;

  /// A searcher who asks to become a provider: there is no searcher admission to give, and
  /// declining only ends the request (they stay a searcher).
  final bool upgrade;
  final void Function(String message, Outcome outcome) onDone;

  @override
  ConsumerState<AdmitControls> createState() => _AdmitControlsState();
}

class _AdmitControlsState extends ConsumerState<AdmitControls> {
  bool _confirming = false;
  bool _busy = false;
  String? _error;

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = leaderProblem(ref.read(appTextProvider), error),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _admit(String to) => _run(() async {
    final result = await ref
        .read(leaderRepositoryProvider)
        .admit(widget.id, to);
    if (!mounted) return;
    widget.onDone(
      ref.read(appTextProvider)('leader.admit.done', {'name': widget.name}),
      Admitted(result),
    );
  });

  Future<void> _decline() => _run(() async {
    await ref.read(leaderRepositoryProvider).decline(widget.id);
    if (!mounted) return;
    widget.onDone(
      ref.read(appTextProvider)(
        widget.upgrade ? 'leader.upgrade.declined' : 'leader.decline.done',
        {'name': widget.name},
      ),
      const Declined(),
    );
  });

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final name = {'name': widget.name};
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_error != null) MessageBanner(_error!),
        if (!_confirming) ...[
          if (!widget.upgrade) ...[
            FilledButton(
              key: Key('admit-searcher-${widget.id}'),
              onPressed: _busy ? null : () => _admit('searcher'),
              child: Text(text('leader.admit.searcher', name)),
            ),
            const SizedBox(height: 8),
          ],
          FilledButton(
            key: Key('admit-provider-${widget.id}'),
            onPressed: _busy || !widget.canAdmitAsProvider
                ? null
                : () => _admit('provider'),
            child: Text(text('leader.admit.provider', name)),
          ),
          if (!widget.canAdmitAsProvider)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(text('leader.admit.providerHint')),
            ),
          const SizedBox(height: 8),
          TextButton(
            key: Key('decline-open-${widget.id}'),
            onPressed: _busy ? null : () => setState(() => _confirming = true),
            child: Text(
              text(
                widget.upgrade
                    ? 'leader.upgrade.decline'
                    : 'leader.decline.open',
                name,
              ),
            ),
          ),
        ] else
          Semantics(
            container: true,
            label: text('leader.decline.open', name),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text(
                    widget.upgrade
                        ? 'leader.upgrade.warning'
                        : 'leader.decline.warning',
                    name,
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton(
                  key: Key('decline-confirm-${widget.id}'),
                  onPressed: _busy ? null : _decline,
                  child: Text(text('leader.decline.confirm')),
                ),
                TextButton(
                  key: Key('decline-cancel-${widget.id}'),
                  onPressed: _busy
                      ? null
                      : () => setState(() => _confirming = false),
                  child: Text(text('common.cancel')),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
