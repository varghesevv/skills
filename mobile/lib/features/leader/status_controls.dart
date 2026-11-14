import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/person_providers.dart';
import 'admit_controls.dart';
import 'data/leader_models.dart';
import 'leader_problem.dart';

const _leads = {'verifier', 'admin', 'owner'};

/// Revoke (after asking), reinstate a revoked person into a group of their church, or confirm a
/// flagged status. The server decides who may; this only hides what cannot work. A leader is not
/// revoked here: they are replaced first.
class StatusControls extends ConsumerStatefulWidget {
  const StatusControls({super.key, required this.detail, required this.onDone});

  final PersonDetail detail;
  final void Function(String message, Outcome outcome) onDone;

  @override
  ConsumerState<StatusControls> createState() => _StatusControlsState();
}

class _StatusControlsState extends ConsumerState<StatusControls> {
  bool _confirming = false;
  bool _busy = false;
  String? _error;
  String _group = '';
  String _to = 'searcher';

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

  String get _name => widget.detail.fullName;

  Future<void> _revoke() => _run(() async {
    await ref.read(leaderRepositoryProvider).revoke(widget.detail.id);
    if (!mounted) return;
    setState(() => _confirming = false);
    widget.onDone(
      ref.read(appTextProvider)('leader.revoke.done', {'name': _name}),
      const StatusChanged(status: 'revoked', homeGroup: null, flagged: false),
    );
  });

  Future<void> _reinstate(List<HomeGroupChoice> groups) => _run(() async {
    final result = await ref
        .read(leaderRepositoryProvider)
        .reinstate(widget.detail.id, _to, _group);
    if (!mounted) return;
    final chosen = groups.where((g) => g.id == _group).firstOrNull;
    widget.onDone(
      ref.read(appTextProvider)('leader.reinstate.done', {'name': _name}),
      StatusChanged(
        status: result.status,
        homeGroup: chosen == null
            ? null
            : IdName(id: chosen.id, name: chosen.name),
        flagged: result.flaggedForRecheck,
      ),
    );
  });

  Future<void> _reconfirm() => _run(() async {
    final result = await ref
        .read(leaderRepositoryProvider)
        .reconfirm(widget.detail.id);
    if (!mounted) return;
    final detail = widget.detail;
    widget.onDone(
      ref.read(appTextProvider)('leader.reconfirm.done', {'name': _name}),
      StatusChanged(
        status: result.status,
        homeGroup: detail.homeGroupId == null
            ? null
            : IdName(id: detail.homeGroupId!, name: detail.homeGroupName ?? ''),
        flagged: result.flaggedForRecheck,
      ),
    );
  });

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final detail = widget.detail;
    final name = {'name': _name};
    final revoked = detail.status == 'revoked';
    final canRevoke =
        !revoked &&
        detail.status != 'pending' &&
        !_leads.contains(detail.status);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_error != null) MessageBanner(_error!),
        if (detail.flaggedForRecheck && !revoked) ...[
          const SizedBox(height: 8),
          Text(text('leader.reconfirm.text', name)),
          const SizedBox(height: 8),
          FilledButton(
            key: const Key('reconfirm'),
            onPressed: _busy ? null : _reconfirm,
            child: Text(text('leader.reconfirm.submit', name)),
          ),
        ],
        if (revoked) _reinstateForm(text, name),
        if (!revoked &&
            _leads.contains(detail.status) &&
            detail.status != 'owner') ...[
          const SizedBox(height: 8),
          Text(text('leader.revoke.leads', name)),
        ],
        if (canRevoke) ...[
          const SizedBox(height: 8),
          if (!_confirming)
            TextButton(
              key: const Key('revoke-open'),
              onPressed: _busy
                  ? null
                  : () => setState(() => _confirming = true),
              child: Text(text('leader.revoke.open', name)),
            )
          else
            Semantics(
              container: true,
              label: text('leader.revoke.open', name),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(text('leader.revoke.warning', name)),
                  const SizedBox(height: 8),
                  FilledButton(
                    key: const Key('revoke-confirm'),
                    onPressed: _busy ? null : _revoke,
                    child: Text(text('leader.revoke.confirm')),
                  ),
                  TextButton(
                    key: const Key('revoke-cancel'),
                    onPressed: _busy
                        ? null
                        : () => setState(() => _confirming = false),
                    child: Text(text('common.cancel')),
                  ),
                ],
              ),
            ),
        ],
      ],
    );
  }

  Widget _reinstateForm(AppText text, Map<String, String> name) {
    final groups = ref.watch(homeGroupsProvider(widget.detail.churchId));
    return groups.when(
      loading: () => Center(
        child: Semantics(
          label: text('config.loading'),
          child: const CircularProgressIndicator(),
        ),
      ),
      error: (error, _) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MessageBanner(ref.read(appTextProvider).error(error)),
          FilledButton(
            key: const Key('retry-groups'),
            onPressed: () =>
                ref.invalidate(homeGroupsProvider(widget.detail.churchId)),
            child: Text(text('common.retry')),
          ),
        ],
      ),
      data: (items) {
        final choices = [
          for (final g in items) HomeGroupChoice(id: g.id, name: g.name),
        ];
        if (choices.isEmpty) {
          return Text(text('leader.reinstate.noGroups'));
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 8),
            Semantics(
              header: true,
              child: Text(
                text('leader.reinstate.title', name),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            DropdownButtonFormField<String>(
              key: const Key('reinstate-group'),
              initialValue: _group,
              decoration: InputDecoration(
                labelText: text('leader.reinstate.group'),
              ),
              items: [
                DropdownMenuItem(
                  value: '',
                  child: Text(text('leader.reinstate.choose')),
                ),
                for (final g in choices)
                  DropdownMenuItem(value: g.id, child: Text(g.name)),
              ],
              onChanged: (value) => setState(() => _group = value ?? ''),
            ),
            DropdownButtonFormField<String>(
              key: const Key('reinstate-status'),
              initialValue: _to,
              decoration: InputDecoration(
                labelText: text('leader.reinstate.status'),
              ),
              items: [
                for (final s in const ['searcher', 'provider'])
                  DropdownMenuItem(value: s, child: Text(text('status.$s'))),
              ],
              onChanged: (value) => setState(() => _to = value ?? 'searcher'),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('reinstate-submit'),
              onPressed: _busy || _group.isEmpty
                  ? null
                  : () => _reinstate(choices),
              child: Text(text('leader.reinstate.submit', name)),
            ),
          ],
        );
      },
    );
  }
}

/// A group a person can be put into: its id and name (the leader's name is not needed here).
class HomeGroupChoice {
  const HomeGroupChoice({required this.id, required this.name});

  final String id;
  final String name;
}
