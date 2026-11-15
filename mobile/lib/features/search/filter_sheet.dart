import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../freelancer/data/label.dart';
import '../freelancer/freelancer_providers.dart';
import '../person/person_providers.dart';
import 'search_models.dart';

/// The filters, in a bottom sheet. They apply when the person presses the button, not as they
/// change, so one search is one request. Pops with the chosen filters, or nothing.
class FilterSheet extends ConsumerStatefulWidget {
  const FilterSheet({super.key, required this.initial});

  final SearchFilters initial;

  @override
  ConsumerState<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends ConsumerState<FilterSheet> {
  late SearchFilters _filters = widget.initial;
  late final _maxRate = TextEditingController(text: widget.initial.maxRate);
  late final _currency = TextEditingController(text: widget.initial.currency);
  String? _rateError;
  String? _currencyError;

  @override
  void dispose() {
    _maxRate.dispose();
    _currency.dispose();
    super.dispose();
  }

  List<String> _toggle(List<String> list, String value) {
    if (list.contains(value)) return [...list]..remove(value);
    return [...list, value];
  }

  void _apply(AppText text) {
    final rate = _maxRate.text.trim();
    final currency = _currency.text.trim();
    String? rateError;
    String? currencyError;
    if (rate.isNotEmpty && !RegExp(r'^\d{1,8}(\.\d{1,2})?$').hasMatch(rate)) {
      rateError = text('validation.rate');
    }
    if (currency.isNotEmpty && !RegExp(r'^[A-Za-z]{3}$').hasMatch(currency)) {
      currencyError = text('validation.currency');
    } else if (rate.isNotEmpty && currency.isEmpty && rateError == null) {
      currencyError = text('search.needCurrency');
    }
    setState(() {
      _rateError = rateError;
      _currencyError = currencyError;
    });
    if (rateError != null || currencyError != null) return;
    if ((_filters.availableFrom == null) != (_filters.availableTo == null)) {
      return;
    }
    Navigator.of(context)
        .pop(_filters.copyWith(maxRate: rate, currency: currency));
  }

  Future<void> _pickDate(bool from) async {
    final now = DateTime.now();
    final chosen = await showDatePicker(
      context: context,
      initialDate:
          (from ? _filters.availableFrom : _filters.availableTo) ?? now,
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365 * 2)),
    );
    if (chosen == null || !mounted) return;
    setState(
      () => _filters = from
          ? _filters.copyWith(availableFrom: chosen)
          : _filters.copyWith(availableTo: chosen),
    );
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final catalog = ref.watch(labelCatalogProvider);
    final churches = ref.watch(churchesProvider);
    final groups = _filters.churchId.isEmpty
        ? null
        : ref.watch(homeGroupsProvider(_filters.churchId));
    final labels = catalog.value ?? const <Label>[];
    List<String> names(String type) => [
      for (final l in labels)
        if (l.type == type) l.name,
    ];
    final levels = sortLevels([
      for (final l in labels)
        if (l.type == 'skill_level') l,
    ]);

    Widget chips(
      String title,
      List<String> options,
      List<String> chosen,
      void Function(List<String>) set,
      String keyPrefix,
    ) {
      if (options.isEmpty) return const SizedBox.shrink();
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          Wrap(
            spacing: 8,
            children: [
              for (final option in options)
                FilterChip(
                  key: Key('$keyPrefix-$option'),
                  label: Text(option),
                  selected: chosen.contains(option),
                  onSelected: (_) => set(_toggle(chosen, option)),
                ),
            ],
          ),
        ],
      );
    }

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: ListView(
          padding: const EdgeInsets.all(16),
          shrinkWrap: true,
          children: [
            Text(
              text('search.filters'),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            chips(
              text('search.skills'),
              names('skill'),
              _filters.skills,
              (v) => setState(() => _filters = _filters.copyWith(skills: v)),
              'skill',
            ),
            if (_filters.skills.length > 1)
              SwitchListTile(
                key: const Key('match-all'),
                contentPadding: EdgeInsets.zero,
                title: Text(text('search.matchAll')),
                value: _filters.matchAll,
                onChanged: (v) =>
                    setState(() => _filters = _filters.copyWith(matchAll: v)),
              ),
            if (levels.isNotEmpty)
              DropdownButtonFormField<String>(
                key: const Key('level'),
                isExpanded: true,
                initialValue: _filters.skillLevel,
                decoration: InputDecoration(labelText: text('search.level')),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(text('search.anyLevel')),
                  ),
                  for (final l in levels)
                    DropdownMenuItem(value: l.name, child: Text(l.name)),
                ],
                onChanged: (v) => setState(
                  () => _filters = _filters.copyWith(skillLevel: v ?? ''),
                ),
              ),
            chips(
              text('search.languages'),
              names('language'),
              _filters.languages,
              (v) => setState(() => _filters = _filters.copyWith(languages: v)),
              'language',
            ),
            chips(
              text('search.timings'),
              names('timing'),
              _filters.timings,
              (v) => setState(() => _filters = _filters.copyWith(timings: v)),
              'timing',
            ),
            chips(
              text('search.nativity'),
              names('nativity'),
              _filters.nativity,
              (v) => setState(() => _filters = _filters.copyWith(nativity: v)),
              'nativity',
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('max-rate'),
              controller: _maxRate,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: text('search.maxRate'),
                errorText: _rateError,
              ),
            ),
            TextField(
              key: const Key('currency'),
              controller: _currency,
              textCapitalization: TextCapitalization.characters,
              maxLength: 3,
              decoration: InputDecoration(
                labelText: text('search.currency'),
                errorText: _currencyError,
              ),
            ),
            SwitchListTile(
              key: const Key('negotiable'),
              contentPadding: EdgeInsets.zero,
              title: Text(text('search.negotiable')),
              value: _filters.negotiable,
              onChanged: (v) =>
                  setState(() => _filters = _filters.copyWith(negotiable: v)),
            ),
            DropdownButtonFormField<String>(
              key: const Key('min-rating'),
              isExpanded: true,
              initialValue: _filters.minRating,
              decoration: InputDecoration(labelText: text('search.minRating')),
              items: [
                DropdownMenuItem(
                  value: '',
                  child: Text(text('search.anyRating')),
                ),
                for (final r in [5, 6, 7, 8, 9])
                  DropdownMenuItem(
                    value: '$r',
                    child: Text(text('search.ratingAtLeast', {'rating': '$r'})),
                  ),
              ],
              onChanged: (v) => setState(
                () => _filters = _filters.copyWith(minRating: v ?? ''),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              text('search.dates'),
              style: Theme.of(context).textTheme.titleSmall,
            ),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  key: const Key('available-from'),
                  onPressed: () => _pickDate(true),
                  child: Text(
                    _filters.availableFrom == null
                        ? text('search.from')
                        : _filters.availableFrom!.toIso8601String().substring(
                            0,
                            10,
                          ),
                  ),
                ),
                OutlinedButton(
                  key: const Key('available-to'),
                  onPressed: () => _pickDate(false),
                  child: Text(
                    _filters.availableTo == null
                        ? text('search.to')
                        : _filters.availableTo!.toIso8601String().substring(
                            0,
                            10,
                          ),
                  ),
                ),
                if (_filters.availableFrom != null ||
                    _filters.availableTo != null)
                  TextButton(
                    key: const Key('clear-dates'),
                    onPressed: () => setState(
                      () => _filters = _filters.copyWith(
                        availableFrom: null,
                        availableTo: null,
                      ),
                    ),
                    child: Text(text('search.clearDates')),
                  ),
              ],
            ),
            if ((_filters.availableFrom == null) !=
                (_filters.availableTo == null))
              Text(text('search.needBothDates')),
            if (churches.value != null && churches.value!.isNotEmpty) ...[
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                key: const Key('church'),
                isExpanded: true,
                initialValue: _filters.churchId,
                decoration: InputDecoration(labelText: text('search.church')),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(text('search.anyChurch')),
                  ),
                  for (final c in churches.value!)
                    DropdownMenuItem(value: c.id, child: Text(c.name)),
                ],
                onChanged: (v) => setState(
                  () => _filters = _filters.copyWith(
                    churchId: v ?? '',
                    homeGroupId: '',
                  ),
                ),
              ),
            ],
            if (groups?.value != null && groups!.value!.isNotEmpty)
              DropdownButtonFormField<String>(
                key: const Key('group'),
                isExpanded: true,
                initialValue: _filters.homeGroupId,
                decoration: InputDecoration(labelText: text('search.group')),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(text('search.anyGroup')),
                  ),
                  for (final g in groups.value!)
                    DropdownMenuItem(value: g.id, child: Text(g.name)),
                ],
                onChanged: (v) => setState(
                  () => _filters = _filters.copyWith(homeGroupId: v ?? ''),
                ),
              ),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('apply-filters'),
              onPressed: () => _apply(text),
              child: Text(text('search.apply')),
            ),
            TextButton(
              key: const Key('clear-filters'),
              onPressed: () => Navigator.of(context)
                  .pop(SearchFilters(name: _filters.name, sort: _filters.sort)),
              child: Text(text('search.clearAll')),
            ),
          ],
        ),
      ),
    );
  }
}
