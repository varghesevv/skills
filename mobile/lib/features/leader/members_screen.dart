import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/leader_models.dart';
import 'leader_paths.dart';

const _filters = ['searcher', 'provider', 'verifier', 'admin', 'owner'];

/// The admitted people in the leader's scope, by name; no numbers in the list.
class MembersScreen extends ConsumerStatefulWidget {
  const MembersScreen({super.key});

  @override
  ConsumerState<MembersScreen> createState() => _MembersScreenState();
}

class _MembersScreenState extends ConsumerState<MembersScreen> {
  List<MemberRow> _items = const [];
  int _total = 0;
  bool _loading = true;
  int _request =
      0; // the latest load; an older answer that arrives later is dropped
  Object? _error;
  bool _failedMore =
      false; // retry the call that failed: a next page, or a reload
  String _status = '';

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
          .read(leaderRepositoryProvider)
          .members(
            offset: more ? _items.length : 0,
            status: _status.isEmpty ? null : _status,
          );
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
    return Scaffold(
      appBar: AppBar(title: Text(text('leader.members.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              DropdownButtonFormField<String>(
                key: const Key('members-filter'),
                initialValue: _status,
                decoration: InputDecoration(
                  labelText: text('leader.members.filter'),
                ),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(text('leader.members.all')),
                  ),
                  for (final value in _filters)
                    DropdownMenuItem(
                      value: value,
                      child: Text(text('status.$value')),
                    ),
                ],
                onChanged: (value) {
                  setState(() => _status = value ?? '');
                  _load();
                },
              ),
              const SizedBox(height: 8),
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
                Text(text('leader.members.none')),
              for (final row in _items)
                ListTile(
                  key: Key('member-${row.id}'),
                  contentPadding: EdgeInsets.zero,
                  title: Text(row.fullName),
                  subtitle: Text(
                    [
                      text('status.${row.status}'),
                      ?row.homeGroupName,
                      if (row.statusSetByName != null)
                        text('leader.members.admittedBy', {
                          'name': row.statusSetByName!,
                        }),
                      if (row.flaggedForRecheck) text('leader.members.flagged'),
                    ].join(' · '),
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () async {
                    await context.push('$leaderPeople/${row.id}');
                    // The page may have changed the person: the list shows what is true now.
                    if (mounted) await _load();
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
