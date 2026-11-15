import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/validation/validators.dart' as rules;
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/message_banner.dart';
import '../../core/api/api_exception.dart';

/// The person's details: name and mobile number can be changed; the address they sign in with is
/// shown and cannot be changed here.
class AccountScreen extends ConsumerStatefulWidget {
  const AccountScreen({super.key});

  @override
  ConsumerState<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends ConsumerState<AccountScreen> {
  late final _name = TextEditingController(
    text: ref.read(personProvider)?.fullName ?? '',
  );
  late final _mobile = TextEditingController(
    text: ref.read(personProvider)?.mobileNumber ?? '',
  );
  String? _nameError;
  String? _mobileError;
  String? _formError;
  bool _busy = false;
  bool _saved = false;

  @override
  void dispose() {
    _name.dispose();
    _mobile.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final text = ref.read(appTextProvider);
    final nameKey = rules.fullName(_name.text);
    final mobileKey = rules.mobile(_mobile.text);
    setState(() {
      _nameError = nameKey == null ? null : text(nameKey);
      _mobileError = mobileKey == null ? null : text(mobileKey);
      _formError = null;
      _saved = false;
    });
    if (nameKey != null || mobileKey != null) return;
    setState(() => _busy = true);
    try {
      final updated = await ref
          .read(personRepositoryProvider)
          .updateMe(
            fullName: _name.text.trim(),
            mobileNumber: rules.normaliseMobile(_mobile.text),
          );
      if (!mounted) return;
      ref.read(sessionProvider.notifier).setPerson(updated);
      setState(() => _saved = true);
    } catch (error) {
      if (mounted) {
        setState(() {
          // The generic answer tells a signed-in person to sign in, which makes no sense here.
          _formError = error is ApiException && error.code == 'account_exists'
              ? text('account.error.taken')
              : text.error(error);
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = ref.watch(personProvider);
    return Scaffold(
      appBar: AppBar(title: Text(text('account.title'))),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(text('account.lead')),
            const SizedBox(height: 12),
            if (_formError != null) MessageBanner(_formError!),
            if (_saved) Text(text('account.saved')),
            AppTextField(
              key: const Key('account-name'),
              label: text('field.fullName'),
              controller: _name,
              error: _nameError,
              capitalization: TextCapitalization.words,
              onChanged: () => setState(() => _saved = false),
            ),
            AppTextField(
              key: const Key('account-mobile'),
              label: text('field.mobile'),
              controller: _mobile,
              error: _mobileError,
              hint: text('field.mobileHint'),
              keyboardType: TextInputType.phone,
              onChanged: () => setState(() => _saved = false),
            ),
            const SizedBox(height: 8),
            Text(
              text('account.email'),
              style: Theme.of(context).textTheme.labelMedium,
            ),
            Text(person?.email ?? ''),
            Text(
              text('account.emailHint'),
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('account-save'),
              onPressed: _busy ? null : _save,
              child: Text(_busy ? text('common.saving') : text('common.save')),
            ),
          ],
        ),
      ),
    );
  }
}
