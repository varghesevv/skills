import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import '../../core/strings/app_text.dart';

/// What a refused closing means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'leads_a_group':
        return text('applicant.leave.error.leadsGroup');
      case 'leads_a_church':
        return text('applicant.leave.error.leadsChurch');
      case 'account_revoked':
        return text('applicant.leave.error.revoked');
    }
  }
  return text.error(error);
}

/// Close one's own account (the store's "delete account"), after asking and with the password.
/// Leaders and the OWNER hand on what they lead first; the server says so and the words follow.
class LeaveAccount extends ConsumerStatefulWidget {
  const LeaveAccount({super.key});

  @override
  ConsumerState<LeaveAccount> createState() => _LeaveAccountState();
}

class _LeaveAccountState extends ConsumerState<LeaveAccount> {
  final _password = TextEditingController();
  final _confirmation = FocusNode();
  final _trigger = FocusNode();
  bool _open = false;
  String? _formError;
  bool _busy = false;

  @override
  void dispose() {
    _password.dispose();
    _confirmation.dispose();
    _trigger.dispose();
    super.dispose();
  }

  void _show() {
    setState(() => _open = true);
    // The confirmation replaces the button: move focus to it.
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _confirmation.requestFocus(),
    );
  }

  void _cancel() {
    setState(() {
      _open = false;
      _formError = null;
      _password.clear();
    });
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _trigger.requestFocus(),
    );
  }

  Future<void> _leave() async {
    final text = ref.read(appTextProvider);
    if (_password.text.isEmpty) {
      return setState(() => _formError = text('validation.required'));
    }
    setState(() {
      _busy = true;
      _formError = null;
    });
    try {
      await ref.read(personRepositoryProvider).closeAccount(_password.text);
    } catch (error) {
      if (mounted) {
        setState(() {
          _formError = _problem(ref.read(appTextProvider), error);
          _busy = false;
        });
      }
      return;
    }
    // The account is closed and every session of it is ended on the server. Forget it here too;
    // a failure of that call must not be shown as a failure to close (it keeps no session).
    try {
      await ref.read(sessionProvider.notifier).logout();
    } on Exception {
      ref.read(sessionProvider.notifier).expire();
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          text('applicant.leave.title'),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(text('applicant.leave.text')),
        const SizedBox(height: 8),
        if (!_open)
          OutlinedButton(
            key: const Key('leave-open'),
            focusNode: _trigger,
            onPressed: _show,
            child: Text(text('applicant.leave.open')),
          )
        else
          Focus(
            focusNode: _confirmation,
            child: Semantics(
              container: true,
              label: text('applicant.leave.title'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(text('applicant.leave.warning')),
                  const SizedBox(height: 8),
                  if (_formError != null) MessageBanner(_formError!),
                  PasswordField(
                    label: text('applicant.leave.confirm'),
                    controller: _password,
                    showLabel: text('field.showPassword'),
                    hideLabel: text('field.hidePassword'),
                    onSubmitted: _busy ? null : _leave,
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    alignment: WrapAlignment.spaceBetween,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    runSpacing: 8,
                    children: [
                      TextButton(
                        key: const Key('leave-cancel'),
                        onPressed: _busy ? null : _cancel,
                        child: Text(text('applicant.leave.cancel')),
                      ),
                      FilledButton(
                        key: const Key('leave-submit'),
                        style: FilledButton.styleFrom(
                          backgroundColor: Theme.of(context).colorScheme.error,
                          foregroundColor: Theme.of(context)
                              .colorScheme
                              .onError,
                        ),
                        onPressed: _busy ? null : _leave,
                        child: Text(
                          _busy
                              ? text('applicant.leave.working')
                              : text('applicant.leave.submit'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
