import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/paged.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import '../freelancer/data/received_rating.dart';
import '../freelancer/freelancer_providers.dart';
import '../leader/leader_providers.dart';
import 'provider_models.dart';
import 'search_controller.dart';

final providerPublicProvider = FutureProvider.autoDispose
    .family<ProviderPublic, String>(
      (ref, id) => ref.watch(searchRepositoryProvider).provider(id),
    );

final _providerRatingsProvider = FutureProvider.autoDispose
    .family<Paged<ReceivedRating>, String>(
      (ref, id) => ref.watch(freelancerRepositoryProvider).ratings(id, page: 1),
    );

/// One provider, as a SEARCHER or above sees them: the facts, labels, availability, the ratings,
/// the caller's own rating (to give or change) and Reveal. A provider sees their own page
/// without the rating form and Reveal, which the server refuses.
class ProviderScreen extends ConsumerWidget {
  const ProviderScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final provider = ref.watch(providerPublicProvider(id));
    final own = ref.watch(personProvider)?.id == id;
    return Scaffold(
      appBar: AppBar(
        title: Text(provider.value?.fullName ?? text('search.noName')),
      ),
      body: SafeArea(
        child: AsyncView<ProviderPublic>(
          value: provider,
          onRetry: () => ref.invalidate(providerPublicProvider(id)),
          builder: (p) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _Facts(provider: p, text: text),
              const SizedBox(height: 16),
              if (!own) ...[_Contact(provider: p), const SizedBox(height: 16)],
              _Labels(provider: p, text: text),
              const SizedBox(height: 16),
              _Unavailable(provider: p, text: text),
              const SizedBox(height: 16),
              if (!own) ...[
                _RatingForm(key: ValueKey(p.id), provider: p),
                const SizedBox(height: 16),
              ],
              _Ratings(id: id, text: text),
            ],
          ),
        ),
      ),
    );
  }
}

class _Facts extends StatelessWidget {
  const _Facts({required this.provider, required this.text});

  final ProviderPublic provider;
  final AppText text;

  @override
  Widget build(BuildContext context) {
    final p = provider;
    final rate = p.ratePerHour == null
        ? text('search.noRate')
        : text('search.rate', {
            'rate': p.ratePerHour!.toStringAsFixed(
              p.ratePerHour! == p.ratePerHour!.roundToDouble() ? 0 : 2,
            ),
            'currency': p.rateCurrency ?? '',
          });
    Widget fact(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Semantics(
        container: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            Text(value),
          ],
        ),
      ),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            fact(
              text('detail.rate'),
              p.isRateNegotiable
                  ? '$rate · ${text('search.negotiableTag')}'
                  : rate,
            ),
            fact(
              text('detail.rating'),
              p.averageRating == null
                  ? text('search.noRatings')
                  : text('search.average', {
                      'average': p.averageRating!.toStringAsFixed(1),
                      'count': '${p.ratingCount}',
                    }),
            ),
            fact(
              text('detail.church'),
              '${p.church.name} · ${p.homeGroup.name}',
            ),
            fact(
              text('detail.nationality'),
              p.nationality ?? text('common.none'),
            ),
            fact(
              text('detail.language'),
              p.primaryLanguage ?? text('common.none'),
            ),
            fact(
              text('detail.whatsapp'),
              p.whatsapp ? text('common.yes') : text('common.no'),
            ),
          ],
        ),
      ),
    );
  }
}

/// A masked number and a Reveal button. The number is asked for only when the button is pressed,
/// is kept in this widget's state alone (never logged, cached or written down), and the phone's
/// dialler opens with it.
class _Contact extends ConsumerStatefulWidget {
  const _Contact({required this.provider});

  final ProviderPublic provider;

  @override
  ConsumerState<_Contact> createState() => _ContactState();
}

class _ContactState extends ConsumerState<_Contact> {
  String? _number;
  String? _error;
  bool _busy = false;

  Future<void> _reveal() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final number = await ref
          .read(searchRepositoryProvider)
          .reveal(widget.provider.id);
      if (!mounted) return;
      setState(() => _number = number);
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(appTextProvider).error(error));
      }
      if (mounted) setState(() => _busy = false);
      return;
    }
    await _dial();
    if (mounted) setState(() => _busy = false);
  }

  /// The reveal is recorded whatever the phone does next: a dialler that cannot open is its own
  /// message, and the number stays on the screen. The Call button comes here too.
  Future<void> _dial() async {
    final number = _number;
    if (number == null) return;
    try {
      await ref.read(dialerProvider)(number);
      if (mounted) setState(() => _error = null);
    } catch (_) {
      if (mounted) {
        setState(() => _error = ref.read(appTextProvider)('reveal.dialFailed'));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text('detail.contact'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            if (_error != null) MessageBanner(_error!),
            if (_number != null)
              Row(
                children: [
                  Expanded(
                    child: SelectableText(
                      _number!,
                      key: const Key('revealed-number'),
                    ),
                  ),
                  IconButton(
                    key: const Key('call'),
                    tooltip: text('reveal.callLabel', {'number': _number!}),
                    icon: const Icon(Icons.call),
                    onPressed: _dial,
                  ),
                ],
              )
            else ...[
              Semantics(
                label: text('reveal.hidden'),
                child: const ExcludeSemantics(child: Text('+•• ••• ••• ••••')),
              ),
              const SizedBox(height: 8),
              FilledButton.tonal(
                key: const Key('reveal'),
                onPressed: _busy ? null : _reveal,
                child: Text(
                  _busy ? text('reveal.working') : text('reveal.button'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Labels extends StatelessWidget {
  const _Labels({required this.provider, required this.text});

  final ProviderPublic provider;
  final AppText text;

  @override
  Widget build(BuildContext context) {
    final labels = provider.labels;
    List<Widget> chips(String type) => [
      for (final l in labels)
        if (l.label.type == type)
          Chip(
            label: Text(
              type == 'skill' && l.level != null
                  ? '${l.label.name} · ${l.level!.name}'
                  : l.label.name,
            ),
          ),
    ];
    Widget group(String title, String type) {
      final items = chips(type);
      if (items.isEmpty) return const SizedBox.shrink();
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          Wrap(spacing: 8, children: items),
        ],
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text('detail.labels'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (labels.isEmpty) Text(text('detail.noLabels')),
            group(text('labels.skill'), 'skill'),
            group(text('labels.language'), 'language'),
            group(text('labels.timing'), 'timing'),
            group(text('labels.nativity'), 'nativity'),
          ],
        ),
      ),
    );
  }
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.provider, required this.text});

  final ProviderPublic provider;
  final AppText text;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text('detail.unavailable'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (provider.unavailable.isEmpty)
            Text(text('detail.alwaysAvailable'))
          else
            for (final period in provider.unavailable)
              Text(
                '${formatPeriodTime(period.from)} → ${formatPeriodTime(period.to)}',
              ),
        ],
      ),
    ),
  );
}

class _RatingForm extends ConsumerStatefulWidget {
  const _RatingForm({super.key, required this.provider});

  final ProviderPublic provider;

  @override
  ConsumerState<_RatingForm> createState() => _RatingFormState();
}

class _RatingFormState extends ConsumerState<_RatingForm> {
  late int? _score = widget.provider.myRating?.rating;
  late final _comment = TextEditingController(
    text: widget.provider.myRating?.comment ?? '',
  );
  String? _error;
  String? _scoreError;
  bool _busy = false;
  bool _saved = false;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final text = ref.read(appTextProvider);
    if (_score == null) {
      setState(() => _scoreError = text('rate.needScore'));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _scoreError = null;
      _saved = false;
    });
    final comment = _comment.text.trim().isEmpty ? null : _comment.text.trim();
    try {
      final repository = ref.read(searchRepositoryProvider);
      final existing = widget.provider.myRating;
      if (existing == null) {
        await repository.rate(widget.provider.id, _score!, comment);
      } else {
        await repository.changeRating(existing.id, _score!, comment);
      }
      if (!mounted) return;
      ref.invalidate(providerPublicProvider(widget.provider.id));
      ref.invalidate(_providerRatingsProvider(widget.provider.id));
      setState(() => _saved = true);
    } catch (error) {
      if (mounted) setState(() => _error = text.error(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final existing = widget.provider.myRating != null;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              existing ? text('rate.edit') : text('rate.new'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (_error != null) MessageBanner(_error!),
            if (_saved) Text(text('rate.saved')),
            DropdownButtonFormField<int>(
              key: const Key('rating-score'),
              isExpanded: true,
              initialValue: _score,
              decoration: InputDecoration(
                labelText: text('rate.score'),
                errorText: _scoreError,
              ),
              items: [
                for (var i = 1; i <= 10; i++)
                  DropdownMenuItem(value: i, child: Text('$i')),
              ],
              onChanged: (v) => setState(() {
                _score = v;
                _saved = false;
              }),
            ),
            TextField(
              key: const Key('rating-comment'),
              controller: _comment,
              maxLength: 2000,
              maxLines: 3,
              decoration: InputDecoration(labelText: text('rate.comment')),
              onChanged: (_) => setState(() => _saved = false),
            ),
            FilledButton(
              key: const Key('rating-save'),
              onPressed: _busy ? null : _save,
              child: Text(
                _busy
                    ? text('common.saving')
                    : existing
                    ? text('rate.submitEdit')
                    : text('rate.submitNew'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Ratings extends ConsumerWidget {
  const _Ratings({required this.id, required this.text});

  final String id;
  final AppText text;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ratings = ref.watch(_providerRatingsProvider(id));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text('detail.ratings'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            InlineAsyncView<Paged<ReceivedRating>>(
              value: ratings,
              onRetry: () => ref.invalidate(_providerRatingsProvider(id)),
              builder: (page) => page.total == 0
                  ? Text(text('detail.noRatings'))
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final r in page.items)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Text(
                              '${text('ratings.score', {'rating': '${r.rating}'})}'
                              ' — ${r.comment ?? text('ratings.noComment')}'
                              ' (${formatDay(r.ratedOn)})',
                            ),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
