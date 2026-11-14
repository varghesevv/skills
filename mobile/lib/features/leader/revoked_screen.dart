import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/format.dart';
import '../../core/providers.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/leader_models.dart';
import 'leader_paths.dart';

/// The revoked people of the leader's scope, with the group they were removed from. A revoked
/// person is brought back from their own page. No numbers in the list.
class RevokedScreen extends ConsumerStatefulWidget {
  const RevokedScreen({super.key});

  @override
  ConsumerState<RevokedScreen> createState() => _RevokedScreenState();
}

class _RevokedScreenState extends ConsumerState<RevokedScreen> {
  List<RevokedRow> _items = const [];
  int _total = 0;
  bool _loading = true;
  int _request = 0;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool more = false}) async {
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref
          .read(leaderRepositoryProvider)
          .revoked(offset: more ? _items.length : 0);
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
      appBar: AppBar(title: Text(text('leader.revoked.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('leader.revoked.lead')),
              const SizedBox(height: 8),
              if (_error != null) ...[
                MessageBanner(text.error(_error!)),
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('retry'),
                  onPressed: () => _load(more: _items.isNotEmpty),
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
                Text(text('leader.revoked.none')),
              for (final row in _items)
                ListTile(
                  key: Key('revoked-${row.id}'),
                  contentPadding: EdgeInsets.zero,
                  title: Text(row.fullName),
                  subtitle: Text(
                    [
                      text('leader.revoked.row', {
                        'group': row.removedFromName ?? '—',
                        'by': row.revokedByName ?? text('leader.history.noone'),
                      }),
                      if (row.revokedAt != null) formatDay(row.revokedAt!),
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
