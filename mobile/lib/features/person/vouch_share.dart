import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/env.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/vouching_models.dart';
import 'person_providers.dart';

/// For an applicant: make a link to share, and see the vouches received so far.
class VouchShare extends ConsumerWidget {
  const VouchShare({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => const Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [_ShareLink(), Divider(height: 32), _Received()],
  );
}

class _ShareLink extends ConsumerStatefulWidget {
  const _ShareLink();

  @override
  ConsumerState<_ShareLink> createState() => _ShareLinkState();
}

class _ShareLinkState extends ConsumerState<_ShareLink> {
  // The token lives only here: it is not in a provider, a route or a log.
  VouchLinkCreated? _created;
  bool _copied = false;
  bool _busy = false;
  String? _error;

  Future<void> _make() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final link = await ref.read(personRepositoryProvider).makeVouchLink();
      if (!mounted) return;
      setState(() {
        _created = link;
        _copied = false;
      });
      ref.invalidate(vouchLinkStateProvider);
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(appTextProvider).error(error));
      }
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
    final state = ref.watch(vouchLinkStateProvider);
    final created = _created;
    final url = created == null
        ? ''
        : vouchLinkFor(created.token, apiBase: Env.apiBaseUrl);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(
            text('vouch.share.title'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        const SizedBox(height: 8),
        Text(text('vouch.share.text')),
        const SizedBox(height: 8),
        InlineAsyncView<VouchLinkState>(
          value: state,
          onRetry: () => ref.invalidate(vouchLinkStateProvider),
          builder: (data) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (created == null)
                Text(
                  data.active && data.expiresAt != null
                      ? text('vouch.share.active', {
                          'date': formatDay(data.expiresAt!),
                        })
                      : text('vouch.share.none'),
                ),
              if (_error != null) MessageBanner(_error!),
              if (created != null) ...[
                MessageBanner(text('vouch.share.once'), kind: BannerKind.info),
                const SizedBox(height: 8),
                Semantics(
                  label: text('vouch.share.label'),
                  child: SelectableText(url, key: const Key('vouch-link')),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  key: const Key('copy-vouch-link'),
                  onPressed: () => _copy(url),
                  icon: const Icon(Icons.copy),
                  label: Text(
                    _copied
                        ? text('vouch.share.copied')
                        : text('vouch.share.copy'),
                  ),
                ),
              ],
              const SizedBox(height: 8),
              OutlinedButton(
                key: const Key('make-vouch-link'),
                onPressed: _busy ? null : _make,
                child: Text(
                  _busy
                      ? text('vouch.share.working')
                      : (data.active || created != null)
                      ? text('vouch.share.again')
                      : text('vouch.share.make'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Received extends ConsumerWidget {
  const _Received();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final received = ref.watch(vouchesReceivedProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(
            text('vouch.received.title'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        const SizedBox(height: 8),
        InlineAsyncView<List<VouchReceived>>(
          value: received,
          onRetry: () => ref.invalidate(vouchesReceivedProvider),
          builder: (items) => items.isEmpty
              ? Text(text('vouch.received.none'))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final vouch in items)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          [
                            text('vouch.received.from', {
                              'name': vouch.voucherName,
                              'church': vouch.churchName,
                            }),
                            formatPeriodTime(vouch.createdAt),
                            if (!vouch.live) text('vouch.received.notCounting'),
                          ].join(' · '),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}
