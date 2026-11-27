import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import 'auth_widgets.dart';

/// A person created from the initial config signs in with a temporary password and is kept here
/// until they choose their own (story S100). The router opens nothing else until then.
class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  ConsumerState<ChangePasswordScreen> createState() =>
      _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _current = TextEditingController();
  final _new = TextEditingController();
  String? _currentKey;
  String? _newKey;
  String? _formError;
  bool _busy = false;

  @override
  void dispose() {
    _current.dispose();
    _new.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _currentKey = requiredPassword(_current.text);
      _newKey = newPassword(_new.text);
      _formError = null;
    });
    if (_currentKey != null || _newKey != null) return;
    setState(() => _busy = true);
    try {
      // On success the session holds the person without the flag: the router leaves this page.
      await ref
          .read(sessionProvider.notifier)
          .changePassword(
            currentPassword: _current.text,
            newPassword: _new.text,
          );
    } catch (error) {
      if (mounted) {
        setState(() => _formError = ref.read(appTextProvider).error(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return AuthPage(
      title: text('changePassword.title'),
      showBack: false,
      children: [
        Text(text('changePassword.text')),
        if (_formError != null) MessageBanner(_formError!),
        PasswordField(
          key: const Key('change-current'),
          label: text('changePassword.current'),
          controller: _current,
          error: _currentKey == null ? null : text(_currentKey!),
          showLabel: text('field.showPassword'),
          hideLabel: text('field.hidePassword'),
          textInputAction: TextInputAction.next,
        ),
        PasswordField(
          key: const Key('change-new'),
          label: text('field.newPassword'),
          controller: _new,
          error: _newKey == null ? null : text(_newKey!),
          hint: text('field.passwordHint'),
          showLabel: text('field.showPassword'),
          hideLabel: text('field.hidePassword'),
          autofillHints: const [AutofillHints.newPassword],
          onSubmitted: _busy ? null : _submit,
        ),
        FilledButton(
          key: const Key('change-submit'),
          onPressed: _busy ? null : _submit,
          child: Text(
            _busy
                ? text('changePassword.working')
                : text('changePassword.submit'),
          ),
        ),
        OutlinedButton(
          key: const Key('change-log-out'),
          onPressed: _busy
              ? null
              : () => ref.read(sessionProvider.notifier).logout(),
          child: Text(text('nav.logOut')),
        ),
      ],
    );
  }
}
