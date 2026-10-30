import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/error_messages.dart';
import '../../../core/providers.dart';
import '../../../shared/widgets/async_view.dart';
import '../../../shared/widgets/message_banner.dart';
import '../data/freelancer_profile.dart';
import '../data/label.dart';
import '../freelancer_providers.dart';

const _groups = [
  ('skill', 'labels.skill'),
  ('language', 'labels.language'),
  ('timing', 'labels.timing'),
  ('nativity', 'labels.nativity'),
];

/// Choose skills (with a level), languages, timings and nativity. Saving replaces the whole
/// selection, as on the web.
class FreelancerLabelsScreen extends ConsumerWidget {
  const FreelancerLabelsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final profile = ref.watch(freelancerProfileProvider);
    final catalog = ref.watch(labelCatalogProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('labels.title'))),
      body: SafeArea(
        child: AsyncView<FreelancerProfile>(
          value: profile,
          onRetry: () => ref.invalidate(freelancerProfileProvider),
          builder: (me) => AsyncView<List<Label>>(
            value: catalog,
            onRetry: () => ref.invalidate(labelCatalogProvider),
            builder: (labels) =>
                _LabelsForm(key: ValueKey(me.id), profile: me, labels: labels),
          ),
        ),
      ),
    );
  }
}

class _LabelsForm extends ConsumerStatefulWidget {
  const _LabelsForm({super.key, required this.profile, required this.labels});

  final FreelancerProfile profile;
  final List<Label> labels;

  @override
  ConsumerState<_LabelsForm> createState() => _LabelsFormState();
}

class _LabelsFormState extends ConsumerState<_LabelsForm> {
  /// label id -> chosen level id (or null)
  late final Map<String, String?> _selection;
  String? _formError;
  bool _busy = false;
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    // A label an admin has since switched off cannot be saved again, so it is dropped here.
    final active = {for (final label in widget.labels) label.id};
    _selection = {
      for (final item in widget.profile.labels)
        if (active.contains(item.label.id))
          item.label.id: item.level != null && active.contains(item.level!.id)
              ? item.level!.id
              : null,
    };
  }

  void _toggle(String id, bool checked) => setState(() {
    _saved = false;
    if (checked) {
      _selection[id] = null;
    } else {
      _selection.remove(id);
    }
  });

  void _setLevel(String id, String? level) => setState(() {
    _saved = false;
    _selection[id] = (level == null || level.isEmpty) ? null : level;
  });

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _formError = null;
      _saved = false;
    });
    try {
      // In the catalogue's order, so the request is the same for the same choice.
      final selection = [
        for (final label in widget.labels)
          if (_selection.containsKey(label.id))
            LabelSelection(labelId: label.id, levelId: _selection[label.id]),
      ];
      await ref.read(freelancerRepositoryProvider).replaceLabels(selection);
      ref.invalidate(freelancerProfileProvider);
      if (mounted) setState(() => _saved = true);
    } catch (error) {
      if (mounted) {
        setState(
          () => _formError = messageFor(error, ref.read(termsProvider)!),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final theme = Theme.of(context);
    final levels = sortLevels([
      for (final l in widget.labels)
        if (l.type == 'skill_level') l,
    ]);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(text('labels.lead')),
        const SizedBox(height: 16),
        for (final (type, titleKey) in _groups)
          _group(text, theme, type, titleKey, levels),
        // Next to the button that was just pressed, so the result is seen on a long list.
        if (_formError != null) ...[
          MessageBanner(_formError!),
          const SizedBox(height: 16),
        ],
        if (_saved) ...[
          MessageBanner(text('common.saved'), kind: BannerKind.success),
          const SizedBox(height: 16),
        ],
        FilledButton(
          key: const Key('labels-save'),
          onPressed: _busy ? null : _save,
          child: Text(_busy ? text('common.saving') : text('common.save')),
        ),
      ],
    );
  }

  Widget _group(
    dynamic text,
    ThemeData theme,
    String type,
    String titleKey,
    List<Label> levels,
  ) {
    final items = [
      for (final l in widget.labels)
        if (l.type == type) l,
    ];
    final count = items.where((l) => _selection.containsKey(l.id)).length;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                header: true,
                child: Text(
                  '${text(titleKey)} (${text('labels.selected', {'count': '$count'})})',
                  style: theme.textTheme.titleMedium,
                ),
              ),
              if (items.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(text('labels.empty')),
                ),
              for (final label in items) ...[
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  value: _selection.containsKey(label.id),
                  onChanged: _busy
                      ? null
                      : (v) => _toggle(label.id, v ?? false),
                  title: Text(label.name),
                ),
                if (type == 'skill' && _selection.containsKey(label.id))
                  Padding(
                    padding: const EdgeInsets.only(left: 40, bottom: 8),
                    child: DropdownButtonFormField<String>(
                      key: Key('level-${label.id}'),
                      initialValue: _selection[label.id] ?? '',
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: text('labels.level', {'skill': label.name}),
                        border: const OutlineInputBorder(),
                      ),
                      items: [
                        DropdownMenuItem(
                          value: '',
                          child: Text(text('labels.noLevel')),
                        ),
                        for (final level in levels)
                          DropdownMenuItem(
                            value: level.id,
                            child: Text(level.name),
                          ),
                      ],
                      onChanged: _busy ? null : (v) => _setLevel(label.id, v),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
