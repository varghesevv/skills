import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/env.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/group_models.dart';

/// What a refused call means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException && error.code == 'no_home_group') {
    return text('invitations.error.noGroup');
  }
  return text.error(error);
}

/// The links a leader sends to people who may join their group. A link is shown once, when it is
/// made; the list shows the links that still work and lets the leader end one.
class InvitationsScreen extends ConsumerStatefulWidget {
  const InvitationsScreen({super.key});

  @override
  ConsumerState<InvitationsScreen> createState() => _InvitationsScreenState();
}

class _InvitationsScreenState extends ConsumerState<InvitationsScreen> {
  List<GroupInvitationRow>? _items;
  Object? _loadError;
  // The token lives only here: it is not in a provider, a route or a log.
  GroupInvitationCreated? _created;
  bool _copied = false;
  bool _busy = false;
  String? _error;
  String? _notice;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loadError = null);
    try {
      final items = await ref.read(groupRepositoryProvider).invitations();
      if (mounted) setState(() => _items = items);
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
    }
  }

  Future<void> _make() async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    final text = ref.read(appTextProvider);
    try {
      final link = await ref.read(groupRepositoryProvider).createInvitation();
      if (!mounted) return;
      setState(() {
        _created = link;
        _copied = false;
      });
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke(String id) async {
    setState(() {
      _busy = true;
      _error = null;
      _notice = null; // an earlier success must not stand next to a new failure
    });
    final text = ref.read(appTextProvider);
    try {
      await ref.read(groupRepositoryProvider).revokeInvitation(id);
      if (!mounted) return;
      setState(() {
        _notice = text('invitations.revoked');
        // The link that was just shown is dead when it is the one that was ended.
        if (_created?.id == id) {
          _created = null;
          _copied = false;
        }
      });
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = _problem(text, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _copy(String url) async {
    await Clipboard.setData(ClipboardData(text: url));
    if (mounted) setState(() => _copied = true);
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final created = _created;
    final url = created == null
        ? ''
        : joinLinkFor(created.token, apiBase: Env.apiBaseUrl);
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: Text(text('invitations.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('invitations.lead')),
              const SizedBox(height: 8),
              if (_error != null) MessageBanner(_error!),
              if (_notice != null)
                MessageBanner(_notice!, kind: BannerKind.success),
              if (created != null) ...[
                MessageBanner(text('invitations.once'), kind: BannerKind.info),
                const SizedBox(height: 8),
                Semantics(
                  label: text('invitations.label'),
                  child: SelectableText(url, key: const Key('join-link')),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  key: const Key('copy-join-link'),
                  onPressed: () => _copy(url),
                  icon: const Icon(Icons.copy),
                  label: Text(
                    _copied
                        ? text('invitations.copied')
                        : text('invitations.copy'),
                  ),
                ),
                Text(
                  text('invitations.until', {
                    'date': formatDay(created.expiresAt),
                  }),
                ),
              ],
              const SizedBox(height: 8),
              OutlinedButton(
                key: const Key('make-join-link'),
                onPressed: _busy ? null : _make,
                child: Text(
                  _busy
                      ? text('invitations.working')
                      : created != null
                      ? text('invitations.again')
                      : text('invitations.make'),
                ),
              ),
              const SizedBox(height: 16),
              Semantics(
                header: true,
                child: Text(
                  text('invitations.list'),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (_loadError != null) ...[
                MessageBanner(_problem(text, _loadError!)),
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('retry'),
                  onPressed: _load,
                  child: Text(text('common.retry')),
                ),
              ] else if (items == null)
                Center(
                  child: Semantics(
                    label: text('config.loading'),
                    child: const CircularProgressIndicator(),
                  ),
                )
              else if (items.isEmpty)
                Text(text('invitations.none'))
              else
                for (final row in items)
                  ListTile(
                    key: Key('invitation-${row.id}'),
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      text('invitations.row', {
                        'made': formatDay(row.createdAt),
                        'until': formatDay(row.expiresAt),
                      }),
                    ),
                    trailing: TextButton(
                      key: Key('revoke-invitation-${row.id}'),
                      onPressed: _busy ? null : () => _revoke(row.id),
                      child: Text(text('invitations.revoke')),
                    ),
                  ),
            ],
          ),
        ),
      ),
    );
  }
}
