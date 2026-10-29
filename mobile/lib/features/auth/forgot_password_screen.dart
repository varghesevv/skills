import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/user_type.dart';
import '../../core/errors/error_messages.dart';
import '../../core/providers.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/message_banner.dart';
import 'auth_widgets.dart';

/// Asks for a reset link. The answer is always the same text, whether or not an account exists.
/// The link itself opens in the browser (version 1).
class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key, required this.type});

  final UserType type;

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _email = TextEditingController();
  String? _emailKey;
  String? _formError;
  bool _busy = false;
  bool _sent = false;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final failed = validateForgotPassword(email: _email.text);
    setState(() {
      _emailKey = failed['email'];
      _formError = null;
    });
    if (failed.isNotEmpty) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(apiClientProvider)
          .post(
            '/auth/forgot-password',
            body: {'email': _email.text.trim(), 'user_type': widget.type.wire},
            auth: false,
          );
      if (mounted) setState(() => _sent = true);
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
    return AuthPage(
      title: text('forgot.title'),
      children: [
        if (_sent) ...[
          MessageBanner(text('forgot.done'), kind: BannerKind.success),
          OutlinedButton(
            onPressed: () => context.pop(),
            child: Text(text('forgot.back')),
          ),
        ] else ...[
          Text(text('forgot.text')),
          if (_formError != null) MessageBanner(_formError!),
          AppTextField(
            label: text('field.email'),
            controller: _email,
            error: _emailKey == null ? null : text(_emailKey!),
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            textInputAction: TextInputAction.done,
            onSubmitted: _busy ? null : _submit,
            enabled: !_busy,
          ),
          FilledButton(
            key: const Key('forgot-submit'),
            onPressed: _busy ? null : _submit,
            child: Text(_busy ? text('forgot.working') : text('forgot.submit')),
          ),
        ],
      ],
    );
  }
}
