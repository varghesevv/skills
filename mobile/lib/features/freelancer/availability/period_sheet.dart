import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/date_time_picker.dart';
import '../../../core/errors/error_messages.dart';
import '../../../core/format.dart';
import '../../../core/providers.dart';
import '../../../core/validation/validators.dart';
import '../../../shared/widgets/message_banner.dart';
import '../data/unavailability.dart';
import '../freelancer_providers.dart';

/// Add or change one unavailable period. Pops `true` after it was saved.
class PeriodSheet extends ConsumerStatefulWidget {
  const PeriodSheet({super.key, required this.editing});

  final Unavailability? editing;

  @override
  ConsumerState<PeriodSheet> createState() => _PeriodSheetState();
}

class _PeriodSheetState extends ConsumerState<PeriodSheet> {
  DateTime? _from;
  DateTime? _to;
  FieldKeys _errors = const {};
  String? _formError;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _from = widget.editing?.from;
    _to = widget.editing?.to;
  }

  Future<void> _choose(bool isFrom) async {
    final picked = await ref.read(dateTimePickerProvider)(
      context,
      isFrom ? _from : (_to ?? _from),
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (isFrom) {
        _from = picked;
      } else {
        _to = picked;
      }
      _errors = const {};
    });
  }

  Future<void> _submit() async {
    final failed = validatePeriod(from: _from, to: _to);
    setState(() {
      _errors = failed;
      _formError = null;
    });
    if (failed.isNotEmpty) return;
    setState(() => _busy = true);
    try {
      final repository = ref.read(freelancerRepositoryProvider);
      final editing = widget.editing;
      if (editing == null) {
        await repository.addUnavailability(_from!, _to!);
      } else {
        await repository.updateUnavailability(editing.id, _from!, _to!);
      }
      ref.invalidate(unavailabilityProvider);
      if (mounted) Navigator.pop(context, true);
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
    final editing = widget.editing != null;
    Widget field(String key, String labelKey, DateTime? value, bool isFrom) {
      final error = _errors[key];
      return Semantics(
        button: true,
        label: text(labelKey),
        child: InkWell(
          key: Key('pick-$key'),
          onTap: _busy ? null : () => _choose(isFrom),
          child: InputDecorator(
            decoration: InputDecoration(
              labelText: text(labelKey),
              errorText: error == null ? null : text(error),
              border: const OutlineInputBorder(),
              suffixIcon: const Icon(Icons.event),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text(
                value == null
                    ? text('availability.choose')
                    : formatPeriodTime(value),
              ),
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(
                text(editing ? 'availability.edit' : 'availability.add'),
                style: theme.textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: 16),
            if (_formError != null) ...[
              MessageBanner(_formError!),
              const SizedBox(height: 16),
            ],
            field('from', 'availability.from', _from, true),
            const SizedBox(height: 16),
            field('to', 'availability.to', _to, false),
            const SizedBox(height: 24),
            FilledButton(
              key: const Key('period-submit'),
              onPressed: _busy ? null : _submit,
              child: Text(
                text(
                  editing
                      ? 'availability.submitEdit'
                      : 'availability.submitAdd',
                ),
              ),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _busy ? null : () => Navigator.pop(context, false),
              child: Text(text('common.cancel')),
            ),
          ],
        ),
      ),
    );
  }
}
