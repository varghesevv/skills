import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/user_type.dart';
import '../../core/errors/error_messages.dart';
import '../../core/providers.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import 'auth_widgets.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key, required this.type});

  final UserType type;

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _mobile = TextEditingController();
  final _password = TextEditingController();
  final _nationality = TextEditingController();
  final _language = TextEditingController();
  bool _whatsapp = false;
  Map<String, String> _errors = const {}; // field -> shown message
  String? _formError;
  bool _busy = false;
  String? _doneKey; // set after the account was created

  bool get _isOrganisation => widget.type == UserType.organisation;
  bool get _isFreelancer => widget.type == UserType.freelancer;

  @override
  void dispose() {
    for (final controller in [
      _name,
      _email,
      _mobile,
      _password,
      _nationality,
      _language,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    final text = ref.read(appTextProvider);
    final failed = validateRegistration(
      type: widget.type.wire,
      name: _name.text,
      email: _email.text,
      mobileNumber: _mobile.text,
      password: _password.text,
      nationality: _nationality.text,
      primaryLanguage: _language.text,
    );
    setState(() {
      _errors = {
        for (final entry in failed.entries) entry.key: text(entry.value),
      };
      _formError = null;
    });
    if (failed.isNotEmpty) return;
    setState(() => _busy = true);
    try {
      final body = <String, Object?>{
        if (_isOrganisation)
          'org_name': _name.text.trim()
        else
          'full_name': _name.text.trim(),
        'email': _email.text.trim(),
        'mobile_number': normaliseMobile(_mobile.text),
        'password': _password.text,
        if (_isFreelancer) ...{
          // Optional text left empty is sent as null so the API stores nothing.
          'nationality': _nationality.text.trim().isEmpty
              ? null
              : _nationality.text.trim(),
          'primary_language': _language.text.trim().isEmpty
              ? null
              : _language.text.trim(),
          'whatsapp_availability': _whatsapp,
        },
      };
      final data = await ref
          .read(apiClientProvider)
          .post('/auth/register/${widget.type.wire}', body: body, auth: false);
      final status = data is Map ? data['approval_status'] : null;
      if (mounted) {
        setState(
          () => _doneKey = status == 'pending'
              ? 'register.done.pending'
              : 'register.done.text',
        );
      }
    } catch (error) {
      final terms = ref.read(termsProvider)!;
      if (mounted) {
        setState(() {
          _errors = {
            ...serverFieldErrors(error),
            if (error is ApiException && error.code == 'email_taken')
              'email': messageFor(error, terms),
          };
          _formError = messageFor(error, terms);
        });
      }
    } finally {
      // The password is not kept once the request is over.
      _password.clear();
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final title = text('register.${widget.type.wire}.title');
    if (_doneKey != null) {
      return AuthPage(
        title: text('register.done.title'),
        showBack: false,
        children: [
          MessageBanner(text(_doneKey!), kind: BannerKind.success),
          FilledButton(
            key: const Key('register-done-login'),
            onPressed: () =>
                context.pushReplacement('/login/${widget.type.wire}'),
            child: Text(text('register.done.login')),
          ),
        ],
      );
    }
    return AuthPage(
      title: title,
      children: [
        if (_formError != null) MessageBanner(_formError!),
        AppTextField(
          label: _isOrganisation
              ? text('field.orgName')
              : text('field.fullName'),
          controller: _name,
          error: _errors[_isOrganisation ? 'org_name' : 'full_name'],
          autofillHints: [
            _isOrganisation
                ? AutofillHints.organizationName
                : AutofillHints.name,
          ],
          enabled: !_busy,
        ),
        AppTextField(
          label: text('field.email'),
          controller: _email,
          error: _errors['email'],
          keyboardType: TextInputType.emailAddress,
          autofillHints: const [AutofillHints.email],
          enabled: !_busy,
        ),
        AppTextField(
          label: text('field.mobile'),
          controller: _mobile,
          error: _errors['mobile_number'],
          hint: text('field.mobileHint'),
          keyboardType: TextInputType.phone,
          autofillHints: const [AutofillHints.telephoneNumber],
          enabled: !_busy,
        ),
        PasswordField(
          label: text('field.password'),
          controller: _password,
          error: _errors['password'],
          hint: text('field.passwordHint'),
          autofillHints: const [AutofillHints.newPassword],
          showLabel: text('field.showPassword'),
          hideLabel: text('field.hidePassword'),
          textInputAction: _isFreelancer
              ? TextInputAction.next
              : TextInputAction.done,
          onSubmitted: _isFreelancer || _busy ? null : _submit,
        ),
        if (_isFreelancer) ...[
          AppTextField(
            label: text('field.nationality'),
            controller: _nationality,
            error: _errors['nationality'],
            enabled: !_busy,
          ),
          AppTextField(
            label: text('field.language'),
            controller: _language,
            error: _errors['primary_language'],
            enabled: !_busy,
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: _whatsapp,
            onChanged: _busy
                ? null
                : (value) => setState(() => _whatsapp = value ?? false),
            title: Text(text('field.whatsapp')),
          ),
        ],
        FilledButton(
          key: const Key('register-submit'),
          onPressed: _busy ? null : _submit,
          child: Text(
            _busy ? text('register.working') : text('register.submit'),
          ),
        ),
        Row(
          children: [
            Flexible(child: Text(text('register.haveAccount'))),
            TextButton(
              onPressed: () =>
                  context.pushReplacement('/login/${widget.type.wire}'),
              child: Text(text('nav.logIn')),
            ),
          ],
        ),
      ],
    );
  }
}
