import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import 'admit_controls.dart';
import 'data/leader_models.dart';
import 'leader_providers.dart';

const _kinds = {
  'signup',
  'admit',
  'appoint',
  'step-down',
  'revoke',
  'reinstate',
  'reconfirm',
  'handover',
  'operator',
};

String _historyText(AppText text, HistoryEntry entry) => text(
  'leader.history',
  {
    'kind': _kinds.contains(entry.kind)
        ? text('leader.history.${entry.kind}')
        : entry.kind,
    'from': entry.fromStatus == null ? '—' : text('status.${entry.fromStatus}'),
    'to': text('status.${entry.toStatus}'),
    'by': entry.changedByName ?? text('leader.history.noone'),
  },
);

/// A searcher who asks to become a provider is waiting for vouches like an applicant.
bool _asksToProvide(PersonDetail d) =>
    d.status == 'searcher' && d.requestedStatus == 'provider';

/// One person in the leader's scope: the number, the history and the chain of trust.
///
/// Every time this screen asks the server the view is recorded, so it asks once. The answer is
/// kept in this screen's own state, not in a provider: the number is gone when the screen is
/// left. After an admission the screen updates itself from the answer instead of asking again.
class PersonDetailScreen extends ConsumerStatefulWidget {
  const PersonDetailScreen({super.key, required this.id});

  final String id;

  @override
  ConsumerState<PersonDetailScreen> createState() => _PersonDetailScreenState();
}

class _PersonDetailScreenState extends ConsumerState<PersonDetailScreen> {
  PersonDetail? _detail;
  Object? _error;
  String? _done;
  bool _declined = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final detail = await ref
          .read(leaderRepositoryProvider)
          .personDetail(widget.id);
      if (mounted) setState(() => _detail = detail);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  void _onDone(String message, Outcome outcome) {
    setState(() {
      _done = message;
      switch (outcome) {
        case Declined():
          _declined = true;
        case Admitted(:final result):
          _detail = _detail?.withStatus(result.status, result.requestedStatus);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final detail = _detail;
    final error = _error;
    final Widget body;
    if (error != null) {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MessageBanner(text.error(error)),
          if (!(error is ApiException && error.status == 404)) ...[
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('retry'),
              onPressed: _load,
              child: Text(text('common.retry')),
            ),
          ],
        ],
      );
    } else if (detail == null) {
      body = Center(
        child: Semantics(
          label: text('config.loading'),
          child: const CircularProgressIndicator(),
        ),
      );
    } else if (_declined) {
      body = MessageBanner(_done!, kind: BannerKind.success);
    } else {
      body = _View(
        detail: detail,
        text: text,
        done: _done,
        onDone: _onDone,
        onCall: () => ref.read(dialerProvider)(detail.mobileNumber),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(detail?.fullName ?? text('leader.person.title')),
      ),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [body]),
      ),
    );
  }
}

class _View extends StatelessWidget {
  const _View({
    required this.detail,
    required this.text,
    required this.done,
    required this.onDone,
    required this.onCall,
  });

  final PersonDetail detail;
  final AppText text;
  final String? done;
  final void Function(String message, Outcome outcome) onDone;
  final VoidCallback onCall;

  Widget _fact(BuildContext context, String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Semantics(
      container: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelMedium),
          Text(value, style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    ),
  );

  Widget _heading(BuildContext context, String label) => Padding(
    padding: const EdgeInsets.only(top: 16, bottom: 4),
    child: Semantics(
      header: true,
      child: Text(label, style: Theme.of(context).textTheme.titleMedium),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (done != null) MessageBanner(done!, kind: BannerKind.success),
        _fact(
          context,
          text('leader.person.status'),
          text('status.${detail.status}'),
        ),
        _fact(context, text('leader.person.church'), detail.churchName),
        _fact(
          context,
          text('leader.person.group'),
          detail.homeGroupName ?? '—',
        ),
        if (detail.requestedStatus != null)
          _fact(
            context,
            text('leader.person.applyingFor'),
            text('vouch.page.goal.${detail.requestedStatus}'),
          ),
        _fact(
          context,
          text('leader.person.setBy'),
          detail.statusSetByName ?? '—',
        ),
        _fact(
          context,
          text('leader.person.applied'),
          formatDay(detail.appliedAt),
        ),
        ListTile(
          key: const Key('call'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.call),
          title: Text(detail.mobileNumber),
          subtitle: Text(text('leader.person.mobile')),
          onTap: onCall,
        ),
        Text(text('leader.person.numberNote')),
        if (detail.status == 'pending' || _asksToProvide(detail)) ...[
          const SizedBox(height: 16),
          AdmitControls(
            id: detail.id,
            name: detail.fullName,
            canAdmitAsProvider: detail.canAdmitAsProvider,
            upgrade: detail.status != 'pending',
            onDone: onDone,
          ),
        ],
        _heading(context, text('leader.person.vouches')),
        if (detail.vouches.isEmpty) Text(text('leader.person.none')),
        for (final voucher in detail.vouches)
          Text(
            [
              text('vouch.received.from', {
                'name': voucher.name,
                'church': voucher.churchName,
              }),
              if (!voucher.live) text('vouch.received.notCounting'),
            ].join(' · '),
          ),
        _heading(context, text('leader.person.history')),
        for (final entry in detail.history)
          Text('${_historyText(text, entry)} · ${formatPeriodTime(entry.at)}'),
        _heading(context, text('leader.person.chain')),
        Text(text('leader.person.chainText')),
        if (detail.chain.isEmpty) Text(text('leader.person.none')),
        for (final link in detail.chain)
          Text(
            '${link.fullName.isEmpty ? '—' : link.fullName} · ${text('status.${link.status}')}',
          ),
      ],
    );
  }
}
