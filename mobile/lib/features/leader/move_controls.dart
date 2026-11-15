import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/person_providers.dart';
import 'admit_controls.dart';
import 'data/leader_models.dart';
import 'leader_problem.dart';

/// An ADMIN or the OWNER move an admitted member who leads nothing to another open group of the
/// church, without the agreements a move by request needs.
class MoveControls extends ConsumerStatefulWidget {
  const MoveControls({super.key, required this.detail, required this.onDone});

  final PersonDetail detail;
  final void Function(String message, Outcome outcome) onDone;

  @override
  ConsumerState<MoveControls> createState() => _MoveControlsState();
}

class _MoveControlsState extends ConsumerState<MoveControls> {
  String _group = '';
  bool _busy = false;
  String? _error;

  String _problem(AppText text, Object error) {
    if (error is ApiException && error.code == 'leads_a_group') {
      return text('admin.move.leads', {'name': widget.detail.fullName});
    }
    return leaderProblem(text, error);
  }

  Future<void> _move() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      final group = await ref
          .read(leaderRepositoryProvider)
          .move(widget.detail.id, _group);
      if (!mounted) return;
      setState(() => _group = '');
      widget.onDone(
        text('admin.move.done', {
          'name': widget.detail.fullName,
          'group': group.name,
        }),
        StatusChanged(
          status: widget.detail.status,
          homeGroup: group,
          flagged: widget.detail.flaggedForRecheck,
          entry: null,
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final detail = widget.detail;
    final groups = ref.watch(homeGroupsProvider(detail.churchId));
    return groups.when(
      loading: () => const SizedBox.shrink(),
      error: (error, _) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MessageBanner(text.error(error)),
          FilledButton(
            key: const Key('retry-move-groups'),
            onPressed: () =>
                ref.invalidate(homeGroupsProvider(detail.churchId)),
            child: Text(text('common.retry')),
          ),
        ],
      ),
      data: (items) {
        final others = items.where((g) => g.id != detail.homeGroupId).toList();
        if (others.isEmpty) return const SizedBox.shrink();
        final group = others.any((g) => g.id == _group) ? _group : '';
        final name = {'name': detail.fullName};
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 16),
            Semantics(
              header: true,
              child: Text(
                text('admin.move.title', name),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            if (_error != null) MessageBanner(_error!),
            DropdownButtonFormField<String>(
              isExpanded: true,
              key: const Key('move-member-to'),
              initialValue: group,
              decoration: InputDecoration(labelText: text('admin.move.to')),
              items: [
                DropdownMenuItem(
                  value: '',
                  child: Text(text('admin.move.choose')),
                ),
                for (final g in others)
                  DropdownMenuItem(value: g.id, child: Text(g.name)),
              ],
              onChanged: (value) => setState(() => _group = value ?? ''),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('move-member'),
              onPressed: _busy || group.isEmpty ? null : _move,
              child: Text(text('admin.move.submit', name)),
            ),
          ],
        );
      },
    );
  }
}
