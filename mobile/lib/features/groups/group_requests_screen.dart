import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/person_me.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../leader/data/leader_models.dart';
import '../person/leads.dart';
import 'data/group_models.dart';

/// What a refused request means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'group_name_taken':
        return text('groupRequests.error.taken');
      case 'request_open':
        return text('groupRequests.error.open');
      case 'successor_required':
        return text('groupRequests.error.successor');
      case 'not_open':
        return text('groupRequests.error.decided');
      case 'requester_unavailable':
        return text('groupRequests.error.gone');
      case 'successor_not_member':
        return text('groupRequests.error.member');
      case 'not_admitted':
        return text('groupRequests.error.admitted');
    }
  }
  return text.error(error);
}

/// Start a home group: a member asks, and the ADMIN of the church (or the OWNER) decides. An ADMIN
/// or the OWNER start one at once. Whoever leads a group now says who leads it from now on.
class GroupRequestsScreen extends ConsumerStatefulWidget {
  const GroupRequestsScreen({super.key});

  @override
  ConsumerState<GroupRequestsScreen> createState() =>
      _GroupRequestsScreenState();
}

class _GroupRequestsScreenState extends ConsumerState<GroupRequestsScreen> {
  List<GroupRequestRow> _items = const [];
  int _total = 0;
  bool _loading = true;
  int _request = 0;
  Object? _error;
  bool _failedMore =
      false; // the failed call was a next page, so retry that and not a reload
  String? _notice;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool more = false}) async {
    final request = ++_request;
    _failedMore = more;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref
          .read(groupRepositoryProvider)
          .requests(offset: more ? _items.length : 0);
      if (!mounted || request != _request) return;
      setState(() {
        _items = more ? [..._items, ...page.items] : page.items;
        _total = page.total;
      });
    } catch (error) {
      if (mounted && request == _request) setState(() => _error = error);
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = ref.watch(personProvider);
    final decides =
        person != null &&
        (person.status == PersonStatus.admin ||
            person.status == PersonStatus.owner);
    return Scaffold(
      appBar: AppBar(title: Text(text('groupRequests.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                decides
                    ? text('groupRequests.leadOwn')
                    : text('groupRequests.lead'),
              ),
              const SizedBox(height: 8),
              if (person != null)
                _AskForm(
                  person: person,
                  decides: decides,
                  onAsked: (message) {
                    setState(() => _notice = message);
                    _load();
                  },
                ),
              const SizedBox(height: 16),
              Semantics(
                header: true,
                child: Text(
                  decides
                      ? text('groupRequests.open')
                      : text('groupRequests.yours'),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (_notice != null)
                MessageBanner(_notice!, kind: BannerKind.success),
              if (_error != null) ...[
                MessageBanner(text.error(_error!)),
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('retry'),
                  onPressed: () => _load(more: _failedMore),
                  child: Text(text('common.retry')),
                ),
              ],
              if (_loading && _items.isEmpty && _error == null)
                Center(
                  child: Semantics(
                    label: text('config.loading'),
                    child: const CircularProgressIndicator(),
                  ),
                ),
              if (!_loading && _error == null && _items.isEmpty)
                Text(text('groupRequests.none')),
              for (final row in _items)
                _RequestTile(
                  key: Key('request-${row.id}'),
                  row: row,
                  decides: decides,
                  onDone: (message) {
                    setState(() => _notice = message);
                    _load();
                  },
                ),
              if (_items.length < _total && _error == null)
                TextButton(
                  key: const Key('show-more'),
                  onPressed: _loading ? null : () => _load(more: true),
                  child: Text(text('leader.more')),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The members of a group, for choosing who leads it. Loaded when the form needs them.
class _Members extends ConsumerStatefulWidget {
  const _Members({
    super.key,
    required this.groupId,
    required this.exclude,
    required this.label,
    required this.noneLabel,
    required this.dropdownKey,
    required this.onChanged,
    required this.onState,
  });

  final String groupId;
  final String exclude;
  final String label;
  final String noneLabel;
  final Key dropdownKey;
  final void Function(String id) onChanged;

  /// Tells the form whether a choice is needed: (loading or failed or others exist).
  final void Function(bool needsChoice) onState;

  @override
  ConsumerState<_Members> createState() => _MembersState();
}

class _MembersState extends ConsumerState<_Members> {
  List<MemberRow>? _rows;
  Object? _error;
  String _chosen = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    widget.onState(true);
    try {
      final page = await ref
          .read(leaderRepositoryProvider)
          .members(homeGroupId: widget.groupId);
      if (!mounted) return;
      final others = page.items.where((m) => m.id != widget.exclude).toList();
      setState(() => _rows = others);
      widget.onState(others.isNotEmpty);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final rows = _rows;
    if (_error != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MessageBanner(text.error(_error!)),
          FilledButton(
            key: const Key('retry-members'),
            onPressed: _load,
            child: Text(text('common.retry')),
          ),
        ],
      );
    }
    if (rows == null) {
      return Center(
        child: Semantics(
          label: text('config.loading'),
          child: const CircularProgressIndicator(),
        ),
      );
    }
    if (rows.isEmpty) return const SizedBox.shrink();
    return DropdownButtonFormField<String>(
      isExpanded: true,
      key: widget.dropdownKey,
      initialValue: _chosen,
      decoration: InputDecoration(labelText: widget.label),
      items: [
        DropdownMenuItem(value: '', child: Text(widget.noneLabel)),
        for (final m in rows)
          DropdownMenuItem(
            value: m.id,
            child: Text('${m.fullName} · ${text('status.${m.status}')}'),
          ),
      ],
      onChanged: (value) {
        setState(() => _chosen = value ?? '');
        widget.onChanged(_chosen);
      },
    );
  }
}

class _AskForm extends ConsumerStatefulWidget {
  const _AskForm({
    required this.person,
    required this.decides,
    required this.onAsked,
  });

  final PersonMe person;
  final bool decides;
  final void Function(String message) onAsked;

  @override
  ConsumerState<_AskForm> createState() => _AskFormState();
}

class _AskFormState extends ConsumerState<_AskForm> {
  final _name = TextEditingController();
  String _successor = '';
  bool _needsSuccessor = false;
  bool _busy = false;
  String? _error;
  int _generation = 0; // a new key resets the members' choice after an answer

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  bool get _leads => widget.decides && leadsOwnGroup(widget.person);

  Future<void> _ask() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      final answer = await ref
          .read(groupRepositoryProvider)
          .ask(
            _name.text.trim(),
            successorId: _leads && _successor.isNotEmpty ? _successor : null,
          );
      if (!mounted) return;
      _name.clear();
      setState(() {
        _successor = '';
        _generation++;
      });
      if (answer.groupName != null) {
        widget.onAsked(
          text('groupRequests.started', {'name': answer.groupName!}),
        );
        // They lead the new group now, so who they are changed too.
        await ref.read(sessionProvider.notifier).refreshPerson();
      } else {
        widget.onAsked(text('groupRequests.asked'));
      }
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final group = widget.person.homeGroup;
    final ready =
        _name.text.trim().length >= 2 &&
        (!_leads || !_needsSuccessor || _successor.isNotEmpty);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_error != null) MessageBanner(_error!),
        TextField(
          key: const Key('group-name'),
          controller: _name,
          maxLength: 200,
          decoration: InputDecoration(labelText: text('groupRequests.name')),
          onChanged: (_) => setState(() {}),
        ),
        if (_leads && group != null)
          _Members(
            key: ValueKey('own-$_generation'),
            groupId: group.id,
            exclude: widget.person.id,
            label: text('groupRequests.successor'),
            noneLabel: text('groupRequests.choose'),
            dropdownKey: const Key('own-successor'),
            onChanged: (id) => setState(() => _successor = id),
            onState: (needs) {
              if (_needsSuccessor != needs) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) setState(() => _needsSuccessor = needs);
                });
              }
            },
          ),
        const SizedBox(height: 8),
        FilledButton(
          key: const Key('ask'),
          onPressed: _busy || !ready ? null : _ask,
          child: Text(
            widget.decides
                ? text('groupRequests.submitOwn')
                : text('groupRequests.submit'),
          ),
        ),
      ],
    );
  }
}

class _RequestTile extends ConsumerStatefulWidget {
  const _RequestTile({
    super.key,
    required this.row,
    required this.decides,
    required this.onDone,
  });

  final GroupRequestRow row;
  final bool decides;
  final void Function(String message) onDone;

  @override
  ConsumerState<_RequestTile> createState() => _RequestTileState();
}

class _RequestTileState extends ConsumerState<_RequestTile> {
  String _successor = '';
  bool _needsChoice = false;
  bool _busy = false;
  String? _error;

  Future<void> _run(Future<String> Function(AppText text) action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      final message = await action(text);
      // The screen may have been left while the answer was on its way.
      if (mounted) widget.onDone(message);
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final row = widget.row;
    final open = row.state == 'open';
    final needsMembers =
        widget.decides &&
        open &&
        row.requesterLeadsAGroup &&
        row.requesterGroup != null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(row.groupName, style: Theme.of(context).textTheme.titleSmall),
          Text(
            [
              if (widget.decides)
                text('groupRequests.by', {
                  'name': row.requesterName,
                  'group': row.groupName,
                }),
              if (widget.decides) row.churchName,
              text('groupRequests.state.${row.state}'),
              formatDay(row.createdAt),
            ].join(' · '),
          ),
          if (_error != null) MessageBanner(_error!),
          if (widget.decides && open) ...[
            if (row.requesterLeadsAGroup)
              Text(text('groupRequests.leads', {'name': row.requesterName})),
            if (needsMembers)
              _Members(
                groupId: row.requesterGroup!.id,
                exclude: row.requesterId,
                label: text('groupRequests.successorOf', {
                  'name': row.requesterName,
                }),
                noneLabel: text('groupRequests.choose'),
                dropdownKey: Key('successor-${row.id}'),
                onChanged: (id) => setState(() => _successor = id),
                onState: (needs) {
                  if (_needsChoice != needs) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (mounted) setState(() => _needsChoice = needs);
                    });
                  }
                },
              ),
            const SizedBox(height: 8),
            FilledButton(
              key: Key('approve-${row.id}'),
              onPressed:
                  _busy || (needsMembers && _needsChoice && _successor.isEmpty)
                  ? null
                  : () => _run((t) async {
                      final name = await ref
                          .read(groupRepositoryProvider)
                          .approve(
                            row.id,
                            successorId: _successor.isEmpty ? null : _successor,
                          );
                      return t('groupRequests.approved', {'name': name});
                    }),
              child: Text(
                text('groupRequests.approve', {'group': row.groupName}),
              ),
            ),
            TextButton(
              key: Key('decline-${row.id}'),
              onPressed: _busy
                  ? null
                  : () => _run((t) async {
                      await ref.read(groupRepositoryProvider).decline(row.id);
                      return t('groupRequests.declined');
                    }),
              child: Text(
                text('groupRequests.decline', {'group': row.groupName}),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
