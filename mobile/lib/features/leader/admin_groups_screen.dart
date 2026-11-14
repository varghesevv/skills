import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/data/person_repository.dart';
import '../person/person_providers.dart';
import 'data/leader_models.dart';

/// What a refused change of leader means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'successor_not_member':
        return text('admin.error.notMember');
      case 'invalid_choice':
        return text('admin.error.choice');
      case 'status_not_allowed':
        return text('leader.error.notAllowed');
      case 'state_changed':
        return text('leader.error.changed');
    }
  }
  return text.error(error);
}

/// The open groups of the ADMIN's church (the OWNER's own church), each with a way to choose who
/// leads it from now on. The old leader stays in the group, as a provider or a searcher, or keeps
/// their status if they are an ADMIN or the OWNER handing on their own group.
class AdminGroupsScreen extends ConsumerStatefulWidget {
  const AdminGroupsScreen({super.key});

  @override
  ConsumerState<AdminGroupsScreen> createState() => _AdminGroupsScreenState();
}

class _AdminGroupsScreenState extends ConsumerState<AdminGroupsScreen> {
  String? _notice;

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = ref.watch(personProvider);
    if (person == null) return const SizedBox.shrink();
    final groups = ref.watch(homeGroupsProvider(person.church.id));
    return Scaffold(
      appBar: AppBar(title: Text(text('admin.groups.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async =>
              ref.refresh(homeGroupsProvider(person.church.id).future),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('admin.groups.lead')),
              if (_notice != null)
                MessageBanner(_notice!, kind: BannerKind.success),
              groups.when(
                loading: () => Center(
                  child: Semantics(
                    label: text('config.loading'),
                    child: const CircularProgressIndicator(),
                  ),
                ),
                error: (error, _) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    MessageBanner(text.error(error)),
                    FilledButton(
                      key: const Key('retry'),
                      onPressed: () =>
                          ref.invalidate(homeGroupsProvider(person.church.id)),
                      child: Text(text('common.retry')),
                    ),
                  ],
                ),
                data: (items) => items.isEmpty
                    ? Text(text('admin.groups.none'))
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (final group in items)
                            _GroupTile(
                              key: Key('group-${group.id}'),
                              group: group,
                              onDone: (message) {
                                setState(() => _notice = message);
                                ref.invalidate(
                                  homeGroupsProvider(person.church.id),
                                );
                              },
                            ),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GroupTile extends ConsumerStatefulWidget {
  const _GroupTile({super.key, required this.group, required this.onDone});

  final HomeGroupSummary group;
  final void Function(String message) onDone;

  @override
  ConsumerState<_GroupTile> createState() => _GroupTileState();
}

class _GroupTileState extends ConsumerState<_GroupTile> {
  bool _open = false;
  List<MemberRow>? _members;
  int _total = 0;
  Object? _loadError;
  String _successor = '';
  String _former = 'provider';
  bool _busy = false;
  String? _error;

  Future<void> _loadMembers() async {
    setState(() => _loadError = null);
    try {
      final page = await ref
          .read(leaderRepositoryProvider)
          .members(homeGroupId: widget.group.id);
      if (mounted) {
        setState(() {
          _members = page.items;
          _total = page.total;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
    }
  }

  void _close() => setState(() {
    _open = false;
    _members = null;
    _loadError = null;
    _successor = '';
    _former = 'provider';
    _error = null;
  });

  Future<void> _change() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      final (group, leader) = await ref
          .read(groupRepositoryProvider)
          .replaceLeader(widget.group.id, _successor, _former);
      if (!mounted) return;
      _close();
      widget.onDone(
        text('admin.groups.done', {'leader': leader, 'group': group}),
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
    final group = widget.group;
    final members = _members;
    // The leader is not a choice. The public list gives only their name, so a leader is told
    // apart from a namesake by their status; the server refuses anything else.
    bool isLeaderRow(MemberRow m) =>
        m.fullName == group.leaderName &&
        const {'verifier', 'admin', 'owner'}.contains(m.status);
    final candidates = [
      for (final m in members ?? const <MemberRow>[])
        if (!isLeaderRow(m)) m,
    ];
    final leader = members?.where(isLeaderRow).firstOrNull;
    final keeps =
        leader != null && const {'admin', 'owner'}.contains(leader.status);
    final formerOptions = leader == null
        ? const ['provider', 'searcher', 'keep']
        : keeps
        ? const ['keep']
        : const ['provider', 'searcher'];
    final former = formerOptions.contains(_former)
        ? _former
        : formerOptions.first;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(group.name, style: Theme.of(context).textTheme.titleMedium),
          Text(text('admin.groups.leader', {'name': group.leaderName})),
          if (!_open)
            TextButton(
              key: Key('replace-${group.id}'),
              onPressed: () {
                setState(() => _open = true);
                _loadMembers();
              },
              child: Text(text('admin.groups.replace', {'group': group.name})),
            )
          else ...[
            if (_error != null) MessageBanner(_error!),
            if (_loadError != null) ...[
              MessageBanner(text.error(_loadError!)),
              FilledButton(
                key: Key('retry-members-${group.id}'),
                onPressed: _loadMembers,
                child: Text(text('common.retry')),
              ),
            ] else if (members == null)
              Center(
                child: Semantics(
                  label: text('config.loading'),
                  child: const CircularProgressIndicator(),
                ),
              )
            else if (candidates.isEmpty)
              Text(text('admin.groups.nobody'))
            else ...[
              if (_total > members.length)
                Text(
                  text('admin.groups.more', {
                    'count': '${members.length}',
                    'total': '$_total',
                  }),
                ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                key: Key('successor-${group.id}'),
                initialValue: _successor,
                decoration: InputDecoration(
                  labelText: text('admin.groups.successor'),
                ),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(text('admin.groups.choose')),
                  ),
                  for (final m in candidates)
                    DropdownMenuItem(
                      value: m.id,
                      child: Text(
                        '${m.fullName} · ${text('status.${m.status}')}',
                      ),
                    ),
                ],
                onChanged: (value) => setState(() => _successor = value ?? ''),
              ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                key: Key('former-${group.id}'),
                initialValue: former,
                decoration: InputDecoration(
                  labelText: text('admin.groups.former'),
                ),
                items: [
                  for (final value in formerOptions)
                    DropdownMenuItem(
                      value: value,
                      child: Text(text('admin.groups.former.$value')),
                    ),
                ],
                onChanged: (value) =>
                    setState(() => _former = value ?? 'provider'),
              ),
              const SizedBox(height: 8),
              FilledButton(
                key: Key('change-${group.id}'),
                onPressed: _busy || _successor.isEmpty ? null : _change,
                child: Text(text('admin.groups.submit')),
              ),
            ],
            TextButton(
              key: Key('close-${group.id}'),
              onPressed: _busy ? null : _close,
              child: Text(text('common.cancel')),
            ),
          ],
        ],
      ),
    );
  }
}
