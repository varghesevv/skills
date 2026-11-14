import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/leader_models.dart';
import 'leader_paths.dart';

/// People whose status was set by someone since revoked. They keep their access; a leader
/// confirms each one from their own page. No numbers in the list.
class FlaggedScreen extends ConsumerStatefulWidget {
  const FlaggedScreen({super.key});

  @override
  ConsumerState<FlaggedScreen> createState() => _FlaggedScreenState();
}

class _FlaggedScreenState extends ConsumerState<FlaggedScreen> {
  List<FlaggedRow> _items = const [];
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
          .flagged(offset: more ? _items.length : 0);
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
      appBar: AppBar(title: Text(text('leader.flagged.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('leader.flagged.lead')),
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
                Text(text('leader.flagged.none')),
              for (final row in _items)
                ListTile(
                  key: Key('flagged-${row.id}'),
                  contentPadding: EdgeInsets.zero,
                  title: Text(row.fullName),
                  subtitle: Text(
                    [
                      text('status.${row.status}'),
                      ?row.homeGroupName,
                      text('leader.flagged.row', {
                        'by':
                            row.statusSetByName ?? text('leader.history.noone'),
                      }),
                    ].join(' · '),
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('$leaderPeople/${row.id}'),
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
