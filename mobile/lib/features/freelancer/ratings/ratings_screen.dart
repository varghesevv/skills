import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/error_messages.dart';
import '../../../core/format.dart';
import '../../../core/providers.dart';
import '../../../shared/widgets/async_view.dart';
import '../../../shared/widgets/message_banner.dart';
import 'ratings_controller.dart';

/// The ratings the freelancer received, newest first, without who gave them.
class RatingsScreen extends ConsumerWidget {
  const RatingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final ratings = ref.watch(ratingsControllerProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('ratings.title'))),
      body: SafeArea(
        child: AsyncView<RatingsState>(
          value: ratings,
          onRetry: () => ref.invalidate(ratingsControllerProvider),
          builder: (state) => RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(ratingsControllerProvider);
              await ref.read(ratingsControllerProvider.future);
            },
            child: _RatingsList(state: state),
          ),
        ),
      ),
    );
  }
}

class _RatingsList extends ConsumerWidget {
  const _RatingsList({required this.state});

  final RatingsState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final theme = Theme.of(context);
    return ListView(
      // Always scrollable, so pull-to-refresh also works on a short or empty list.
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text(text('ratings.lead')),
        const SizedBox(height: 16),
        if (state.total == 0)
          Text(text('ratings.empty'))
        else ...[
          Text(text('ratings.count', {'count': '${state.total}'})),
          const SizedBox(height: 8),
          for (final item in state.items)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const ExcludeSemantics(
                          child: Icon(Icons.star, size: 20),
                        ),
                        const SizedBox(width: 8),
                        // Expanded: at large text the score wraps instead of running off the card.
                        Expanded(
                          child: Text(
                            text('ratings.score', {'rating': '${item.rating}'}),
                            style: theme.textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(item.comment ?? text('ratings.noComment')),
                    const SizedBox(height: 8),
                    Text(
                      formatDay(item.ratedOn),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          if (state.loadMoreError != null) ...[
            const SizedBox(height: 8),
            MessageBanner(
              messageFor(state.loadMoreError!, ref.watch(termsProvider)!),
            ),
          ],
          if (state.hasMore) ...[
            const SizedBox(height: 8),
            Text(
              text('ratings.showing', {
                'shown': '${state.items.length}',
                'total': '${state.total}',
              }),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Center(
              child: state.loadingMore
                  ? Semantics(
                      label: text('config.loading'),
                      child: const CircularProgressIndicator(),
                    )
                  : OutlinedButton(
                      key: const Key('show-more'),
                      onPressed: () => ref
                          .read(ratingsControllerProvider.notifier)
                          .loadMore(),
                      child: Text(text('common.showMore')),
                    ),
            ),
          ],
        ],
      ],
    );
  }
}
