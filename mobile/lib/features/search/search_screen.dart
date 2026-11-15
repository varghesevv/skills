import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/person_providers.dart';
import 'filter_sheet.dart';
import 'search_controller.dart';
import 'search_models.dart';

/// Find providers: the filters of the API, a search by name, removable chips, a sort and pages.
/// For a SEARCHER and everyone above, over every church.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _name = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  void _apply(SearchFilters filters) =>
      ref.read(searchFiltersProvider.notifier).set(filters);

  Future<void> _openFilters() async {
    final chosen = await showModalBottomSheet<SearchFilters>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => FilterSheet(initial: ref.read(searchFiltersProvider)),
    );
    if (chosen != null) _apply(chosen);
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final filters = ref.watch(searchFiltersProvider);
    final results = ref.watch(searchControllerProvider);
    final churches = ref.watch(churchesProvider).value ?? const [];
    final groups = filters.churchId.isEmpty
        ? const []
        : (ref.watch(homeGroupsProvider(filters.churchId)).value ?? const []);
    final me = ref.watch(personProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('search.title'))),
      body: SafeArea(
        child: AsyncView<SearchState>(
          value: results,
          onRetry: () => ref.invalidate(searchControllerProvider),
          builder: (state) => RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(searchControllerProvider);
              await ref.read(searchControllerProvider.future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Text(text('search.lead')),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('search-name'),
                  controller: _name,
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    labelText: text('search.name'),
                    suffixIcon: IconButton(
                      key: const Key('search-go'),
                      tooltip: text('search.nameGo'),
                      icon: const Icon(Icons.search),
                      onPressed: () =>
                          _apply(filters.copyWith(name: _name.text.trim())),
                    ),
                  ),
                  onSubmitted: (v) => _apply(filters.copyWith(name: v.trim())),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    OutlinedButton.icon(
                      key: const Key('open-filters'),
                      onPressed: _openFilters,
                      icon: const Icon(Icons.tune),
                      label: Text(
                        filters.activeCount > 0
                            ? text('search.filtersActive', {
                                'count': '${filters.activeCount}',
                              })
                            : text('search.filters'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: DropdownButtonFormField<SearchSort>(
                        key: const Key('sort'),
                        isExpanded: true,
                        initialValue: filters.sort,
                        decoration: InputDecoration(
                          labelText: text('search.sort'),
                        ),
                        items: [
                          for (final s in SearchSort.values)
                            DropdownMenuItem(
                              value: s,
                              child: Text(text('search.sort.${s.name}')),
                            ),
                        ],
                        onChanged: (v) {
                          if (v != null) _apply(filters.copyWith(sort: v));
                        },
                      ),
                    ),
                  ],
                ),
                _Chips(
                  filters: filters,
                  churchName: churches
                      .where((c) => c.id == filters.churchId)
                      .map((c) => c.name)
                      .firstOrNull,
                  groupName: groups
                      .where((g) => g.id == filters.homeGroupId)
                      .map((g) => g.name)
                      .firstOrNull,
                  onChange: (updated) {
                    _name.text = updated.name;
                    _apply(updated);
                  },
                ),
                const SizedBox(height: 8),
                if (state.total == 0) ...[
                  Text(text('search.none')),
                  if (filters.activeCount > 0 || filters.name.isNotEmpty)
                    TextButton(
                      key: const Key('clear-all'),
                      onPressed: () {
                        _name.clear();
                        _apply(SearchFilters(sort: filters.sort));
                      },
                      child: Text(text('search.clearAll')),
                    ),
                ] else ...[
                  Text(text('search.results', {'count': '${state.total}'})),
                  const SizedBox(height: 8),
                  for (final (index, item) in state.items.indexed)
                    _ResultCard(
                      key: Key('result-$index'),
                      item: item,
                      text: text,
                      own: item.id == me?.id,
                    ),
                  if (state.loadMoreError != null) ...[
                    const SizedBox(height: 8),
                    MessageBanner(text.error(state.loadMoreError!)),
                  ],
                  if (state.hasMore) ...[
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
                                  .read(searchControllerProvider.notifier)
                                  .loadMore(),
                              child: Text(text('common.showMore')),
                            ),
                    ),
                  ],
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// One chip per filter in force; the person removes a single one with a tap.
class _Chips extends StatelessWidget {
  const _Chips({
    required this.filters,
    required this.churchName,
    required this.groupName,
    required this.onChange,
  });

  final SearchFilters filters;
  final String? churchName;
  final String? groupName;
  final void Function(SearchFilters) onChange;

  @override
  Widget build(BuildContext context) {
    final chips = <(String key, String label, SearchFilters Function() without)>[
      if (filters.name.isNotEmpty)
        ('name', filters.name, () => filters.copyWith(name: '')),
      for (final s in filters.skills)
        (
          'skill-$s',
          s,
          () => filters.copyWith(skills: [...filters.skills]..remove(s)),
        ),
      if (filters.skillLevel.isNotEmpty)
        ('level', filters.skillLevel, () => filters.copyWith(skillLevel: '')),
      for (final l in filters.languages)
        (
          'language-$l',
          l,
          () => filters.copyWith(languages: [...filters.languages]..remove(l)),
        ),
      for (final t in filters.timings)
        (
          'timing-$t',
          t,
          () => filters.copyWith(timings: [...filters.timings]..remove(t)),
        ),
      for (final n in filters.nativity)
        (
          'nativity-$n',
          n,
          () => filters.copyWith(nativity: [...filters.nativity]..remove(n)),
        ),
      if (filters.maxRate.isNotEmpty)
        (
          'rate',
          '≤ ${filters.maxRate} ${filters.currency.toUpperCase()}',
          () => filters.copyWith(maxRate: '', currency: ''),
        ),
      if (filters.maxRate.isEmpty && filters.currency.isNotEmpty)
        (
          'currency',
          filters.currency.toUpperCase(),
          () => filters.copyWith(currency: ''),
        ),
      if (filters.negotiable)
        ('negotiable', '✓', () => filters.copyWith(negotiable: false)),
      if (filters.minRating.isNotEmpty)
        (
          'rating',
          '≥ ${filters.minRating}',
          () => filters.copyWith(minRating: ''),
        ),
      if (filters.availableFrom != null && filters.availableTo != null)
        (
          'dates',
          '${filters.availableFrom!.toIso8601String().substring(0, 10)} → ${filters.availableTo!.toIso8601String().substring(0, 10)}',
          () => filters.copyWith(availableFrom: null, availableTo: null),
        ),
      if (filters.churchId.isNotEmpty)
        (
          'church',
          churchName ?? '…',
          () => filters.copyWith(churchId: '', homeGroupId: ''),
        ),
      if (filters.homeGroupId.isNotEmpty)
        ('group', groupName ?? '…', () => filters.copyWith(homeGroupId: '')),
    ];
    if (chips.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Wrap(
        spacing: 8,
        children: [
          for (final chip in chips)
            InputChip(
              key: Key('chip-${chip.$1}'),
              label: Text(chip.$2),
              onDeleted: () => onChange(chip.$3()),
              deleteButtonTooltipMessage: chip.$2,
            ),
        ],
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({
    super.key,
    required this.item,
    required this.text,
    required this.own,
  });

  final SearchResultItem item;
  final AppText text;
  final bool own;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rate = item.ratePerHour == null
        ? text('search.noRate')
        : text('search.rate', {
            'rate': item.ratePerHour!.toStringAsFixed(
              item.ratePerHour! == item.ratePerHour!.roundToDouble() ? 0 : 2,
            ),
            'currency': item.rateCurrency ?? '',
          });
    return Card(
      child: MergeSemantics(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.fullName ?? text('search.noName'),
                style: theme.textTheme.titleMedium,
              ),
              Text(
                '${item.church.name} · ${item.homeGroup.name}',
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: 4),
              Text(
                item.isRateNegotiable
                    ? '$rate · ${text('search.negotiableTag')}'
                    : rate,
              ),
              Text(
                item.averageRating == null
                    ? text('search.noRatings')
                    : text('search.average', {
                        'average': item.averageRating!.toStringAsFixed(1),
                        'count': '${item.ratingCount}',
                      }),
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 8,
                children: [
                  for (final s in item.skills)
                    Chip(
                      label: Text(
                        s.level == null ? s.name : '${s.name} · ${s.level}',
                      ),
                    ),
                ],
              ),
              if (own) Text(text('search.own')),
            ],
          ),
        ),
      ),
    );
  }
}
