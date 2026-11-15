import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/paged.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/person_router_paths.dart';
import 'provider_models.dart';
import 'search_controller.dart';

/// The ratings loaded so far; each page is asked for once.
class GivenState {
  const GivenState({
    required this.items,
    required this.total,
    this.loadingMore = false,
    this.loadMoreError,
  });

  final List<GivenRating> items;
  final int total;
  final bool loadingMore;
  final Object? loadMoreError;

  bool get hasMore => items.length < total;
}

class GivenController extends AsyncNotifier<GivenState> {
  int _loadedPages = 0;
  int _generation = 0;

  @override
  Future<GivenState> build() async {
    final generation = ++_generation;
    _loadedPages = 0;
    final Paged<GivenRating> page = await ref
        .read(searchRepositoryProvider)
        .givenRatings(page: 1);
    if (generation == _generation) _loadedPages = 1;
    return GivenState(items: page.items, total: page.total);
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || current.loadingMore || !current.hasMore) return;
    final generation = _generation;
    final pageToLoad = _loadedPages + 1;
    state = AsyncData(
      GivenState(items: current.items, total: current.total, loadingMore: true),
    );
    GivenState Function(GivenState latest) next;
    try {
      final page = await ref
          .read(searchRepositoryProvider)
          .givenRatings(page: pageToLoad);
      next = (latest) => GivenState(
        items: [...latest.items, ...page.items],
        total: page.total,
      );
    } catch (error) {
      next = (latest) => GivenState(
        items: latest.items,
        total: latest.total,
        loadMoreError: error,
      );
    }
    if (!ref.mounted || generation != _generation) return;
    final latest = state.value;
    if (latest == null) return;
    final built = next(latest);
    if (built.loadMoreError == null) _loadedPages = pageToLoad;
    state = AsyncData(built);
  }
}

final givenControllerProvider =
    AsyncNotifierProvider.autoDispose<GivenController, GivenState>(
      GivenController.new,
    );

/// The ratings the person gave. Each opens the provider, so it can be changed there.
class RatingsGivenScreen extends ConsumerWidget {
  const RatingsGivenScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final given = ref.watch(givenControllerProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('given.title'))),
      body: SafeArea(
        child: AsyncView<GivenState>(
          value: given,
          onRetry: () => ref.invalidate(givenControllerProvider),
          builder: (state) => RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(givenControllerProvider);
              await ref.read(givenControllerProvider.future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Text(text('given.lead')),
                const SizedBox(height: 12),
                if (state.total == 0)
                  Text(text('given.empty'))
                else ...[
                  for (final (index, r) in state.items.indexed)
                    Card(
                      key: Key('given-$index'),
                      child: InkWell(
                        onTap: () async {
                          await context.push(
                            '$personProviders/${r.providerId}',
                          );
                          // The rating may have been changed there: ask again.
                          if (context.mounted) {
                            ref.invalidate(givenControllerProvider);
                          }
                        },
                        child: MergeSemantics(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  r.providerName ?? text('search.noName'),
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium,
                                ),
                                Text(
                                  text('ratings.score', {
                                    'rating': '${r.rating}',
                                  }),
                                ),
                                Text(r.comment ?? text('ratings.noComment')),
                                Text(
                                  formatDay(r.ratedOn),
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (state.loadMoreError != null) ...[
                    const SizedBox(height: 8),
                    MessageBanner(text.error(state.loadMoreError!)),
                  ],
                  if (state.hasMore)
                    Center(
                      child: state.loadingMore
                          ? Semantics(
                              label: text('config.loading'),
                              child: const CircularProgressIndicator(),
                            )
                          : OutlinedButton(
                              key: const Key('show-more'),
                              onPressed: () => ref
                                  .read(givenControllerProvider.notifier)
                                  .loadMore(),
                              child: Text(text('common.showMore')),
                            ),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
