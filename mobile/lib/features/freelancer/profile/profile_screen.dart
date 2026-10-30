import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/error_messages.dart';
import '../../../core/providers.dart';
import '../../../core/validation/validators.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/async_view.dart';
import '../../../shared/widgets/message_banner.dart';
import '../data/freelancer_profile.dart';
import '../freelancer_providers.dart';

/// Currencies offered as suggestions. Any three-letter code may be typed.
const _currencies = [
  'AED',
  'USD',
  'EUR',
  'GBP',
  'INR',
  'SAR',
  'QAR',
  'KWD',
  'BHD',
  'OMR',
  'PHP', //
]; // fmt: skip

class FreelancerProfileScreen extends ConsumerWidget {
  const FreelancerProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final profile = ref.watch(freelancerProfileProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('profile.title'))),
      body: SafeArea(
        child: AsyncView<FreelancerProfile>(
          value: profile,
          onRetry: () => ref.invalidate(freelancerProfileProvider),
          builder: (data) =>
              _ProfileForm(key: ValueKey(data.id), profile: data),
        ),
      ),
    );
  }
}

class _ProfileForm extends ConsumerStatefulWidget {
  const _ProfileForm({super.key, required this.profile});

  final FreelancerProfile profile;

  @override
  ConsumerState<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends ConsumerState<_ProfileForm> {
  late final _name = TextEditingController();
  late final _mobile = TextEditingController();
  late final _nationality = TextEditingController();
  late final _language = TextEditingController();
  late final _rate = TextEditingController();
  late final _currency = TextEditingController();
  final _currencyFocus = FocusNode();
  late bool _whatsapp;
  late bool _negotiable;
  Map<String, String> _errors = const {}; // field -> shown message
  String? _formError;
  bool _busy = false;
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    _fill(widget.profile);
  }

  void _fill(FreelancerProfile p) {
    _name.text = p.fullName ?? '';
    _mobile.text = p.mobileNumber;
    _nationality.text = p.nationality ?? '';
    _language.text = p.primaryLanguage ?? '';
    final rate = p.ratePerHour;
    // 45.0 is shown as 45, 45.5 as 45.5.
    _rate.text = rate == null
        ? ''
        : (rate == rate.roundToDouble()
              ? rate.toInt().toString()
              : rate.toString());
    _currency.text = p.rateCurrency ?? '';
    _whatsapp = p.whatsappAvailability;
    _negotiable = p.isRateNegotiable;
  }

  @override
  void dispose() {
    for (final c in [
      _name,
      _mobile,
      _nationality,
      _language,
      _rate,
      _currency,
    ]) {
      c.dispose();
    }
    _currencyFocus.dispose();
    super.dispose();
  }

  void _edited() {
    if (_saved) setState(() => _saved = false);
  }

  Future<void> _save() async {
    final text = ref.read(appTextProvider);
    final failed = validateFreelancerProfile(
      fullNameValue: _name.text,
      mobileNumber: _mobile.text,
      nationality: _nationality.text,
      primaryLanguage: _language.text,
      ratePerHour: _rate.text,
      rateCurrency: _currency.text,
    );
    setState(() {
      _errors = {for (final e in failed.entries) e.key: text(e.value)};
      _formError = null;
      _saved = false;
    });
    if (failed.isNotEmpty) return;
    String? orNull(String v) => v.trim().isEmpty ? null : v.trim();
    final rateText = _rate.text.trim();
    final update = FreelancerProfileUpdate(
      fullName: _name.text.trim(),
      mobileNumber: normaliseMobile(_mobile.text),
      whatsappAvailability: _whatsapp,
      nationality: orNull(_nationality.text),
      primaryLanguage: orNull(_language.text),
      ratePerHour: rateText.isEmpty ? null : double.parse(rateText),
      rateCurrency: orNull(normaliseCurrency(_currency.text)),
      isRateNegotiable: _negotiable,
    );
    setState(() => _busy = true);
    try {
      final saved = await ref
          .read(freelancerRepositoryProvider)
          .updateProfile(update);
      if (!mounted) return;
      setState(() {
        _fill(saved);
        _saved = true;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _errors = serverFieldErrors(error);
        _formError = messageFor(error, ref.read(termsProvider)!);
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final theme = Theme.of(context);
    Widget gap(Widget child) =>
        Padding(padding: const EdgeInsets.only(bottom: 16), child: child);
    return ListView(
      padding: const EdgeInsets.all(16),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      children: [
        gap(Text(text('profile.lead'))),
        if (_formError != null) gap(MessageBanner(_formError!)),
        if (_saved)
          gap(MessageBanner(text('common.saved'), kind: BannerKind.success)),
        gap(Text(text('profile.contact'), style: theme.textTheme.titleMedium)),
        gap(
          AppTextField(
            label: text('field.fullName'),
            controller: _name,
            error: _errors['full_name'],
            autofillHints: const [AutofillHints.name],
            enabled: !_busy,
            onChanged: _edited,
          ),
        ),
        gap(
          AppTextField(
            label: text('field.mobile'),
            controller: _mobile,
            error: _errors['mobile_number'],
            hint: text('field.mobileHint'),
            keyboardType: TextInputType.phone,
            autofillHints: const [AutofillHints.telephoneNumber],
            enabled: !_busy,
            onChanged: _edited,
          ),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: _whatsapp,
          onChanged: _busy
              ? null
              : (v) {
                  _edited();
                  setState(() => _whatsapp = v ?? false);
                },
          title: Text(text('field.whatsapp')),
        ),
        const SizedBox(height: 8),
        gap(
          AppTextField(
            label: text('profile.nationality'),
            controller: _nationality,
            error: _errors['nationality'],
            enabled: !_busy,
            onChanged: _edited,
          ),
        ),
        gap(
          AppTextField(
            label: text('profile.language'),
            controller: _language,
            error: _errors['primary_language'],
            enabled: !_busy,
            onChanged: _edited,
          ),
        ),
        gap(
          Text(text('profile.rateSection'), style: theme.textTheme.titleMedium),
        ),
        gap(
          AppTextField(
            label: text('profile.rate'),
            controller: _rate,
            error: _errors['rate_per_hour'],
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            enabled: !_busy,
            onChanged: _edited,
          ),
        ),
        gap(
          RawAutocomplete<String>(
            textEditingController: _currency,
            focusNode: _currencyFocus,
            optionsBuilder: (value) {
              final typed = value.text.trim().toUpperCase();
              return _currencies.where(
                (c) => c.startsWith(typed) && c != typed,
              );
            },
            onSelected: (_) => _edited(),
            fieldViewBuilder: (context, controller, focus, onSubmit) =>
                AppTextField(
                  label: text('profile.currency'),
                  controller: controller,
                  focusNode: focus,
                  error: _errors['rate_currency'],
                  hint: text('profile.currencyHint'),
                  capitalization: TextCapitalization.characters,
                  maxLength: 3,
                  enabled: !_busy,
                  onChanged: _edited,
                ),
            optionsViewBuilder: (context, onSelected, options) => Align(
              alignment: Alignment.topLeft,
              child: Material(
                elevation: 4,
                child: SizedBox(
                  width: 200,
                  child: ListView(
                    padding: EdgeInsets.zero,
                    shrinkWrap: true,
                    children: [
                      for (final option in options)
                        ListTile(
                          title: Text(option),
                          onTap: () => onSelected(option),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: _negotiable,
          onChanged: _busy
              ? null
              : (v) {
                  _edited();
                  setState(() => _negotiable = v ?? false);
                },
          title: Text(text('profile.negotiable')),
        ),
        const SizedBox(height: 8),
        FilledButton(
          key: const Key('profile-save'),
          onPressed: _busy ? null : _save,
          child: Text(_busy ? text('common.saving') : text('common.save')),
        ),
      ],
    );
  }
}
