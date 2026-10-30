import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/user_type.dart';
import '../../core/errors/error_messages.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import 'auth_widgets.dart';

/// Email and password for one kind of account. The route fixes the account type, so a person on
/// the organisation screen can only log in as an organisation.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, required this.type});

  final UserType type;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
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
          .login(
            email: _email.text.trim(),
            password: _password.text,
            type: widget.type,
          );
      // The router sees the new session and moves to the dashboard.
    } catch (error) {
      if (mounted) {
        // A wrong password is not kept in the field.
        _password.clear();
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
    String? error(String field) {
      final key = _errors[field];
      return key == null ? null : text(key);
    }

    return AuthPage(
      title: text('login.title'),
      children: [
        Text(
          text('role.${widget.type.wire}'),
          style: Theme.of(context).textTheme.titleLarge,
        ),
        if (widget.type == UserType.organisation)
          MessageBanner(text('login.org.text'), kind: BannerKind.info),
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
          key: const Key('login-submit'),
          onPressed: _busy ? null : _submit,
          child: Text(_busy ? text('login.working') : text('login.submit')),
        ),
        TextButton(
          onPressed: () => context.push('/forgot-password/${widget.type.wire}'),
          child: Text(text('login.forgot')),
        ),
        Row(
          children: [
            Flexible(child: Text(text('login.noAccount'))),
            TextButton(
              onPressed: () =>
                  context.pushReplacement('/register/${widget.type.wire}'),
              child: Text(text('nav.register')),
            ),
          ],
        ),
      ],
    );
  }
}
