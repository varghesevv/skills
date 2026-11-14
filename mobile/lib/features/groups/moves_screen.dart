import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/person_me.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/leads.dart';
import '../person/person_providers.dart';
import 'data/group_models.dart';

/// What a refused move means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'request_open':
        return text('moves.error.open');
      case 'not_open':
        return text('moves.error.notOpen');
      case 'already_agreed':
        return text('moves.error.agreed');
      case 'request_stale':
        return text('moves.error.stale');
      case 'invalid_choice':
        return text('moves.error.same');
      case 'leads_a_group':
        return text('moves.ask.leads');
      case 'not_admitted':
        return text('groupRequests.error.admitted');
    }
  }
  return text.error(error);
}

/// Move to another group of the church by agreement: the member asks (which is their own
/// agreement) and the leaders of both groups agree. A leader hands their group on first.
class MovesScreen extends ConsumerStatefulWidget {
  const MovesScreen({super.key});

  @override
  ConsumerState<MovesScreen> createState() => _MovesScreenState();
}

class _MovesScreenState extends ConsumerState<MovesScreen> {
  List<MoveRow> _items = const [];
  int _total = 0;
  bool _loading = true;
  int _request = 0;
  Object? _error;
  bool _failedMore =
      false; // retry the call that failed: a next page, or a reload
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
          .moves(offset: more ? _items.length : 0);
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
    return Scaffold(
      appBar: AppBar(title: Text(text('moves.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('moves.lead')),
              const SizedBox(height: 8),
              if (person != null)
                _AskForm(
                  person: person,
                  onAsked: () {
                    setState(() => _notice = text('moves.ask.done'));
                    _load();
                  },
                ),
              const SizedBox(height: 16),
              Semantics(
                header: true,
                child: Text(
                  text('moves.list'),
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
                Text(text('moves.none')),
              if (person != null)
                for (final row in _items)
                  _MoveTile(
                    key: Key('move-${row.id}'),
                    row: row,
                    person: person,
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

class _AskForm extends ConsumerStatefulWidget {
  const _AskForm({required this.person, required this.onAsked});

  final PersonMe person;
  final VoidCallback onAsked;

  @override
  ConsumerState<_AskForm> createState() => _AskFormState();
}

class _AskFormState extends ConsumerState<_AskForm> {
  String _group = '';
  bool _busy = false;
  String? _error;

  Future<void> _ask() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      await ref.read(groupRepositoryProvider).askToMove(_group);
      if (!mounted) return;
      setState(() => _group = '');
      widget.onAsked();
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = widget.person;
    if (leadsOwnGroup(person)) return Text(text('moves.ask.leads'));
    final groups = ref.watch(homeGroupsProvider(person.church.id));
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
          MessageBanner(text.error(error)),
          FilledButton(
            key: const Key('retry-groups'),
            onPressed: () =>
                ref.invalidate(homeGroupsProvider(person.church.id)),
            child: Text(text('common.retry')),
          ),
        ],
      ),
      data: (items) {
        final others = items
            .where((g) => g.id != person.homeGroup?.id)
            .toList();
        if (others.isEmpty) return Text(text('moves.ask.none'));
        // A group that is no longer offered (closed meanwhile) cannot stay chosen.
        final group = others.any((g) => g.id == _group) ? _group : '';
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_error != null) MessageBanner(_error!),
            DropdownButtonFormField<String>(
              isExpanded: true,
              key: const Key('move-to'),
              initialValue: group,
              decoration: InputDecoration(labelText: text('moves.ask.to')),
              items: [
                DropdownMenuItem(
                  value: '',
                  child: Text(text('moves.ask.choose')),
                ),
                for (final g in others)
                  DropdownMenuItem(value: g.id, child: Text(g.name)),
              ],
              onChanged: (value) => setState(() => _group = value ?? ''),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('move-ask'),
              onPressed: _busy || group.isEmpty ? null : _ask,
              child: Text(text('moves.ask.submit')),
            ),
          ],
        );
      },
    );
  }
}

class _MoveTile extends ConsumerStatefulWidget {
  const _MoveTile({
    super.key,
    required this.row,
    required this.person,
    required this.onDone,
  });

  final MoveRow row;
  final PersonMe person;
  final void Function(String message) onDone;

  @override
  ConsumerState<_MoveTile> createState() => _MoveTileState();
}

class _MoveTileState extends ConsumerState<_MoveTile> {
  bool _busy = false;
  String? _error;

  Future<void> _run(Future<String> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    try {
      widget.onDone(await action());
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
    final person = widget.person;
    final open = row.state == 'open';
    // A leader acts for the group they lead: the one the member leaves or the one they join.
    final mine = person.homeGroup?.id;
    final leads = leadsOwnGroup(person) && mine != null;
    final leavesMine = leads && mine == row.fromGroup.id;
    final joinsMine = leads && mine == row.toGroup.id;
    final canAgree =
        open &&
        ((leavesMine && !row.agreedFromLeader) ||
            (joinsMine && !row.agreedToLeader));
    final canCancel =
        open && (row.personId == person.id || leavesMine || joinsMine);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text('moves.row', {
              'name': row.personName,
              'from': row.fromGroup.name,
              'to': row.toGroup.name,
            }),
            style: Theme.of(context).textTheme.titleSmall,
          ),
          Text(
            '${text('moves.state.${row.state}')} · ${formatDay(row.createdAt)}',
          ),
          if (open) ...[
            Text(text('moves.agreed.person')),
            Text(
              row.agreedFromLeader
                  ? text('moves.agreed.from')
                  : text('moves.waiting.from'),
            ),
            Text(
              row.agreedToLeader
                  ? text('moves.agreed.to')
                  : text('moves.waiting.to'),
            ),
          ],
          if (_error != null) MessageBanner(_error!),
          if (canAgree)
            FilledButton(
              key: Key('agree-${row.id}'),
              onPressed: _busy
                  ? null
                  : () => _run(() async {
                      final moved = await ref
                          .read(groupRepositoryProvider)
                          .agree(row.id);
                      final t = ref.read(appTextProvider);
                      return moved.state == 'completed'
                          ? t('moves.moved', {'name': row.personName})
                          : t('moves.agreed', {'name': row.personName});
                    }),
              child: Text(text('moves.agree', {'name': row.personName})),
            ),
          if (canCancel)
            TextButton(
              key: Key('cancel-${row.id}'),
              onPressed: _busy
                  ? null
                  : () => _run(() async {
                      await ref.read(groupRepositoryProvider).cancel(row.id);
                      return ref.read(appTextProvider)('moves.cancelled');
                    }),
              child: Text(text('moves.cancel', {'name': row.personName})),
            ),
        ],
      ),
    );
  }
}
