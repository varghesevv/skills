import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/error_messages.dart';
import '../../../core/format.dart';
import '../../../core/providers.dart';
import '../../../shared/widgets/async_view.dart';
import '../data/unavailability.dart';
import '../freelancer_providers.dart';
import 'period_sheet.dart';

/// The freelancer's unavailable periods, as a list (a month calendar does not fit a phone).
class AvailabilityScreen extends ConsumerWidget {
  const AvailabilityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final periods = ref.watch(unavailabilityProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('availability.title'))),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('add-period'),
        onPressed: () => _openSheet(context, ref, null),
        icon: const Icon(Icons.add),
        label: Text(text('availability.add')),
      ),
      body: SafeArea(
        child: AsyncView<List<Unavailability>>(
          value: periods,
          onRetry: () => ref.invalidate(unavailabilityProvider),
          builder: (list) => _PeriodList(
            periods: list,
            onEdit: (period) => _openSheet(context, ref, period),
            onDelete: (period) => _confirmDelete(context, ref, period),
          ),
        ),
      ),
    );
  }

  Future<void> _openSheet(
    BuildContext context,
    WidgetRef ref,
    Unavailability? editing,
  ) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => PeriodSheet(editing: editing),
    );
    if (saved == true && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ref.read(appTextProvider)('common.saved'))),
      );
    }
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    Unavailability period,
  ) async {
    final text = ref.read(appTextProvider);
    final messenger = ScaffoldMessenger.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: Text(text('availability.deleteTitle')),
        content: Text(
          text('availability.period', {
            'from': formatPeriodTime(period.from),
            'to': formatPeriodTime(period.to),
          }),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: Text(text('common.cancel')),
          ),
          FilledButton(
            key: const Key('confirm-delete'),
            onPressed: () => Navigator.pop(dialog, true),
            child: Text(text('common.confirmDelete')),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    // Everything the answer needs is read before waiting: a screen that is closed meanwhile
    // (sign-out, back) must not touch its `ref` or `context` afterwards.
    final repository = ref.read(freelancerRepositoryProvider);
    final terms = ref.read(termsProvider)!;
    String? failure;
    try {
      await repository.deleteUnavailability(period.id);
    } catch (error) {
      failure = messageFor(error, terms);
    }
    if (!context.mounted) return;
    // On an error too: a period that is already gone (deleted on another device) just
    // disappears from the list.
    ref.invalidate(unavailabilityProvider);
    if (failure != null) {
      messenger.showSnackBar(SnackBar(content: Text(failure)));
    }
  }
}

class _PeriodList extends ConsumerWidget {
  const _PeriodList({
    required this.periods,
    required this.onEdit,
    required this.onDelete,
  });

  final List<Unavailability> periods;
  final void Function(Unavailability) onEdit;
  final void Function(Unavailability) onDelete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final theme = Theme.of(context);
    return ListView(
      // Room under the last card for the floating button.
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
      children: [
        Text(text('availability.lead')),
        const SizedBox(height: 16),
        Semantics(
          header: true,
          child: Text(
            text('availability.list'),
            style: theme.textTheme.titleMedium,
          ),
        ),
        const SizedBox(height: 8),
        if (periods.isEmpty) Text(text('availability.empty')),
        for (final period in periods)
          Card(
            key: Key('period-${period.id}'),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Semantics(
                      container: true,
                      child: Text(
                        text('availability.period', {
                          'from': formatPeriodTime(period.from),
                          'to': formatPeriodTime(period.to),
                        }),
                      ),
                    ),
                  ),
                  IconButton(
                    key: Key('edit-${period.id}'),
                    tooltip: text('common.edit'),
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: () => onEdit(period),
                  ),
                  IconButton(
                    key: Key('delete-${period.id}'),
                    tooltip: text('common.delete'),
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => onDelete(period),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
