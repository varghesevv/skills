import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/vouching_models.dart';
import 'person_providers.dart';

/// The vouches a member gave. One can be taken back until the person is admitted.
class MyVouchesScreen extends ConsumerStatefulWidget {
  const MyVouchesScreen({super.key});

  @override
  ConsumerState<MyVouchesScreen> createState() => _MyVouchesScreenState();
}

class _MyVouchesScreenState extends ConsumerState<MyVouchesScreen> {
  String? _error;
  bool _busy = false;

  Future<void> _withdraw(VouchGiven vouch) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(personRepositoryProvider).withdrawVouch(vouch.id);
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(appTextProvider).error(error));
      }
    } finally {
      // The screen may have been left while the request ran; the provider disposes itself then.
      if (mounted) {
        ref.invalidate(vouchesGivenProvider);
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final given = ref.watch(vouchesGivenProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('vouch.given.title'))),
      body: SafeArea(
        child: AsyncView<List<VouchGiven>>(
          value: given,
          onRetry: () => ref.invalidate(vouchesGivenProvider),
          builder: (items) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_error != null) MessageBanner(_error!),
              if (items.isEmpty) Text(text('vouch.given.none')),
              for (final vouch in items) _row(text, vouch),
            ],
          ),
        ),
      ),
    );
  }

  Widget _row(AppText text, VouchGiven vouch) {
    final name = vouch.applicantName.isEmpty
        ? text('notifications.someone')
        : vouch.applicantName;
    final status = vouch.withdrawn
        ? text('vouch.given.withdrawn')
        : vouch.canWithdraw
        ? text('status.pending')
        : text('vouch.given.decided');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${text('vouch.given.status', {'name': name, 'status': status})} · ${formatDay(vouch.createdAt)}',
          ),
          if (vouch.canWithdraw && !vouch.withdrawn)
            TextButton(
              onPressed: _busy ? null : () => _withdraw(vouch),
              child: Text(text('vouch.given.withdraw', {'name': name})),
            ),
        ],
      ),
    );
  }
}
