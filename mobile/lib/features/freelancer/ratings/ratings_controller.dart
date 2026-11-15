import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/session/session_controller.dart';
import '../data/received_rating.dart';
import '../freelancer_providers.dart';

/// The ratings loaded so far, and whether more are being fetched.
///
/// Immutable; each change builds a whole new value, so nothing (an old error, for example) is
/// carried over by accident.
class RatingsState {
  const RatingsState({
    required this.items,
    required this.total,
    this.loadingMore = false,
    this.loadMoreError,
  });

  final List<ReceivedRating> items;
  final int total;
  final bool loadingMore;

  /// The error of the last "Show more", kept next to the ratings already shown.
  final Object? loadMoreError;

  bool get hasMore => items.length < total;
}

/// Loads the first page, then more on request. The list is dropped when the screen closes.
class RatingsController extends AsyncNotifier<RatingsState> {
  int _loadedPages = 0;

  /// Counts rebuilds (refresh, new session). A "Show more" answer that arrives after a rebuild
  /// belongs to the old list and is thrown away.
  int _generation = 0;

  @override
  Future<RatingsState> build() async {
    final generation = ++_generation;
    _loadedPages = 0;
    // A person of the church trust model, or an account of the older kind until it is removed.
    // Only the identity matters: a refresh of the person must not drop the pages shown.
    final id =
        ref.watch(personProvider.select((person) => person?.id)) ??
        ref.watch(meProvider.select((me) => me?.id));
    if (id == null) return const RatingsState(items: [], total: 0);
    final page = await ref
        .read(freelancerRepositoryProvider)
        .ratings(id, page: 1);
    if (generation == _generation) _loadedPages = 1;
    return RatingsState(items: page.items, total: page.total);
  }

  Future<void> loadMore() async {
    final current = state.value;
    final id = ref.read(personProvider)?.id ?? ref.read(meProvider)?.id;
    if (current == null ||
        id == null ||
        current.loadingMore ||
        !current.hasMore) {
      return;
    }
    final generation = _generation;
    final pageToLoad = _loadedPages + 1;
    state = AsyncData(
      RatingsState(
        items: current.items,
        total: current.total,
        loadingMore: true,
      ),
    );
    RatingsState Function(RatingsState latest) next;
    try {
      final page = await ref
          .read(freelancerRepositoryProvider)
          .ratings(id, page: pageToLoad);
      next = (latest) => RatingsState(
        items: [...latest.items, ...page.items],
        total: page.total,
      );
    } catch (error) {
      // Keep what is on screen; the person can try again.
      next = (latest) => RatingsState(
        items: latest.items,
        total: latest.total,
        loadMoreError: error,
      );
    }
    // The list may have been refreshed, the session changed or the screen closed while waiting:
    // then this answer is for a list that no longer exists. Never write it, and never touch the
    // page counter of the new one.
    if (!ref.mounted || generation != _generation) return;
    final latest = state.value;
    if (latest == null) return;
    final result = next(latest);
    if (result.loadMoreError == null) _loadedPages = pageToLoad;
    state = AsyncData(result);
  }
}

final ratingsControllerProvider =
    AsyncNotifierProvider.autoDispose<RatingsController, RatingsState>(
      RatingsController.new,
    );
