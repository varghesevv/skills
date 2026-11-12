import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/session/session_controller.dart';
import '../data/received_rating.dart';
import '../freelancer_providers.dart';

/// The ratings loaded so far, and whether more are being fetched.
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

  RatingsState copyWith({
    List<ReceivedRating>? items,
    int? total,
    bool? loadingMore,
    Object? loadMoreError,
    bool clearError = false,
  }) => RatingsState(
    items: items ?? this.items,
    total: total ?? this.total,
    loadingMore: loadingMore ?? this.loadingMore,
    loadMoreError: clearError ? null : (loadMoreError ?? this.loadMoreError),
  );
}

/// Loads the first page, then more on request. The list is dropped when the screen closes.
class RatingsController extends AsyncNotifier<RatingsState> {
  int _loadedPages = 0;

  @override
  Future<RatingsState> build() async {
    _loadedPages = 0;
    final me = ref.watch(sessionProvider).value;
    if (me == null) return const RatingsState(items: [], total: 0);
    final page = await ref
        .read(freelancerRepositoryProvider)
        .ratings(me.id, page: 1);
    _loadedPages = 1;
    return RatingsState(items: page.items, total: page.total);
  }

  Future<void> loadMore() async {
    final current = state.value;
    final me = ref.read(sessionProvider).value;
    if (current == null ||
        me == null ||
        current.loadingMore ||
        !current.hasMore) {
      return;
    }
    state = AsyncData(current.copyWith(loadingMore: true, clearError: true));
    try {
      final page = await ref
          .read(freelancerRepositoryProvider)
          .ratings(me.id, page: _loadedPages + 1);
      _loadedPages += 1;
      state = AsyncData(
        current.copyWith(
          items: [...current.items, ...page.items],
          total: page.total,
          loadingMore: false,
          // `current` was taken before the earlier error was cleared: clear it here too.
          clearError: true,
        ),
      );
    } catch (error) {
      // Keep what is on screen; the person can try again.
      state = AsyncData(
        current.copyWith(loadingMore: false, loadMoreError: error),
      );
    }
  }
}

final ratingsControllerProvider =
    AsyncNotifierProvider.autoDispose<RatingsController, RatingsState>(
      RatingsController.new,
    );
