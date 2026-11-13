import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import 'admit_controls.dart';
import 'data/leader_models.dart';
import 'leader_paths.dart';

/// The people waiting in the leader's scope, the most vouched first, with admit and decline.
class ApplicantsScreen extends ConsumerStatefulWidget {
  const ApplicantsScreen({super.key});

  @override
  ConsumerState<ApplicantsScreen> createState() => _ApplicantsScreenState();
}

class _ApplicantsScreenState extends ConsumerState<ApplicantsScreen> {
  List<ApplicantRow> _items = const [];
  int _total = 0;
  bool _loading = true;
  Object? _error;
  String? _done;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool more = false}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref
          .read(leaderRepositoryProvider)
          .applicants(offset: more ? _items.length : 0);
      if (!mounted) return;
      setState(() {
        _items = more ? [..._items, ...page.items] : page.items;
        _total = page.total;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _decided(ApplicantRow row, String message) {
    setState(() {
      _done = message;
      _items = [
        for (final item in _items)
          if (item.id != row.id) item,
      ];
      _total = _total > 0 ? _total - 1 : 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('leader.applicants.title'))),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(text('leader.applicants.lead')),
              const SizedBox(height: 8),
              if (_done != null)
                MessageBanner(_done!, kind: BannerKind.success),
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
                Text(text('leader.applicants.none')),
              for (final row in _items)
                _Applicant(
                  row: row,
                  text: text,
                  onDone: (message, _) => _decided(row, message),
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

class _Applicant extends StatelessWidget {
  const _Applicant({
    required this.row,
    required this.text,
    required this.onDone,
  });

  final ApplicantRow row;
  final AppText text;
  final void Function(String message, Outcome outcome) onDone;

  @override
  Widget build(BuildContext context) {
    final goal = text('vouch.page.goal.${row.requestedStatus ?? 'searcher'}');
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(
                row.fullName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              [
                text('leader.applicant.goal', {'goal': goal}),
                text('leader.applicant.group', {'group': row.homeGroup.name}),
                text('leader.applicant.applied', {
                  'date': formatDay(row.appliedAt),
                }),
              ].join(' · '),
            ),
            Text(
              [
                row.vouchCount == 1
                    ? text('applicant.vouchCount.one')
                    : text('applicant.vouchCount', {
                        'count': '${row.vouchCount}',
                      }),
                if (row.vouchers.isEmpty) text('leader.applicant.noVouches'),
              ].join(' · '),
            ),
            for (final voucher in row.vouchers)
              Text(
                [
                  text('vouch.received.from', {
                    'name': voucher.name,
                    'church': voucher.churchName,
                  }),
                  if (!voucher.live) text('vouch.received.notCounting'),
                ].join(' · '),
              ),
            TextButton(
              key: Key('details-${row.id}'),
              onPressed: () => context.push('$leaderPeople/${row.id}'),
              child: Text(
                text('leader.applicant.details', {'name': row.fullName}),
              ),
            ),
            AdmitControls(
              id: row.id,
              name: row.fullName,
              canAdmitAsProvider: row.canAdmitAsProvider,
              upgrade: row.status != 'pending',
              onDone: onDone,
            ),
          ],
        ),
      ),
    );
  }
}
