import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import '../auth/auth_widgets.dart';

/// The one login for every person: email and password, no account type.
class PersonSignInScreen extends ConsumerStatefulWidget {
  const PersonSignInScreen({super.key});

  @override
  ConsumerState<PersonSignInScreen> createState() => _PersonSignInScreenState();
}

class _PersonSignInScreenState extends ConsumerState<PersonSignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  FieldKeys _errors = const {};
  String? _formError;
  bool _busy = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final failed = validateLogin(email: _email.text, password: _password.text);
    setState(() {
      _errors = failed;
      _formError = null;
    });
    if (failed.isNotEmpty) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(sessionProvider.notifier)
          .loginPerson(email: _email.text.trim(), password: _password.text);
      // The router sees the new session and moves to the home of the person.
    } catch (error) {
      if (mounted) {
        _password.clear(); // a wrong password is not kept in the field
        setState(() => _formError = ref.read(appTextProvider).error(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    String? error(String field) {
      final key = _errors[field];
      return key == null ? null : text(key);
    }

    return AuthPage(
      title: text('member.signIn.title'),
      children: [
        Text(text('member.signIn.text')),
        if (_formError != null) MessageBanner(_formError!),
        AppTextField(
          label: text('field.email'),
          controller: _email,
          error: error('email'),
          keyboardType: TextInputType.emailAddress,
          autofillHints: const [AutofillHints.username, AutofillHints.email],
          enabled: !_busy,
        ),
        PasswordField(
          label: text('field.password'),
          controller: _password,
          error: error('password'),
          showLabel: text('field.showPassword'),
          hideLabel: text('field.hidePassword'),
          onSubmitted: _busy ? null : _submit,
        ),
        FilledButton(
          key: const Key('member-login-submit'),
          onPressed: _busy ? null : _submit,
          child: Text(_busy ? text('login.working') : text('login.submit')),
        ),
        TextButton(
          onPressed: () => context.push('/forgot-password'),
          child: Text(text('login.forgot')),
        ),
        Row(
          children: [
            Flexible(child: Text(text('member.signIn.noAccount'))),
            TextButton(
              onPressed: () => context.pushReplacement('/sign-up'),
              child: Text(text('member.signUp.title')),
            ),
          ],
        ),
      ],
    );
  }
}
