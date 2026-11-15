import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'search_models.dart';
import 'search_repository.dart';

final searchRepositoryProvider = Provider<SearchRepository>(
  (ref) => SearchRepository(ref.watch(apiClientProvider)),
);

/// The filters in force. Dropped when the screen closes, like the results.
class SearchFiltersNotifier extends Notifier<SearchFilters> {
  @override
  SearchFilters build() => const SearchFilters();

  void set(SearchFilters filters) => state = filters;
}

final searchFiltersProvider =
    NotifierProvider.autoDispose<SearchFiltersNotifier, SearchFilters>(
      SearchFiltersNotifier.new,
    );

/// The results loaded so far, and whether more are being fetched. Immutable.
class SearchState {
  const SearchState({
    required this.items,
    required this.total,
    this.loadingMore = false,
    this.loadMoreError,
  });

  final List<SearchResultItem> items;
  final int total;
  final bool loadingMore;
  final Object? loadMoreError;

  bool get hasMore => items.length < total;
}

class SearchController extends AsyncNotifier<SearchState> {
  int _loadedPages = 0;

  /// Counts rebuilds (new filters). An answer for older filters is thrown away.
  int _generation = 0;

  @override
  Future<SearchState> build() async {
    final generation = ++_generation;
    _loadedPages = 0;
    final filters = ref.watch(searchFiltersProvider);
    final page = await ref
        .read(searchRepositoryProvider)
        .search(filters, page: 1);
    if (generation == _generation) _loadedPages = 1;
    return SearchState(items: page.items, total: page.total);
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || current.loadingMore || !current.hasMore) return;
    final generation = _generation;
    final filters = ref.read(searchFiltersProvider);
    final pageToLoad = _loadedPages + 1;
    state = AsyncData(
      SearchState(
        items: current.items,
        total: current.total,
        loadingMore: true,
      ),
    );
    SearchState Function(SearchState latest) next;
    try {
      final page = await ref
          .read(searchRepositoryProvider)
          .search(filters, page: pageToLoad);
      next = (latest) => SearchState(
        items: [...latest.items, ...page.items],
        total: page.total,
      );
    } catch (error) {
      // Keep what is on screen; the person can try again.
      next = (latest) => SearchState(
        items: latest.items,
        total: latest.total,
        loadMoreError: error,
      );
    }
    // The filters changed or the screen closed while this ran: the answer belongs to a list that
    // no longer exists.
    if (!ref.mounted || generation != _generation) return;
    final latest = state.value;
    if (latest == null) return;
    final built = next(latest);
    if (built.loadMoreError == null) _loadedPages = pageToLoad;
    state = AsyncData(built);
  }
}

final searchControllerProvider =
    AsyncNotifierProvider.autoDispose<SearchController, SearchState>(
      SearchController.new,
    );
