import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../core/validation/validators.dart';
import '../../shared/widgets/app_text_field.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import '../../shared/widgets/password_field.dart';
import '../auth/auth_widgets.dart';
import 'data/person_repository.dart';
import 'person_providers.dart';

enum _Step { details, church, group, status }

/// Joining: about you, then the church and the home group (an invitation link skips both), then
/// whether to find providers or offer skills. The new person is pending until the leader of the
/// chosen home group admits them.
class SignUpScreen extends ConsumerStatefulWidget {
  const SignUpScreen({super.key, this.invitationToken});

  final String? invitationToken;

  @override
  ConsumerState<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends ConsumerState<SignUpScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _mobile = TextEditingController();
  final _password = TextEditingController();
  _Step _step = _Step.details;
  String? _churchId;
  String? _groupId;
  String _applied = 'searcher';
  FieldKeys _errors = const {};
  String? _formError;
  bool _busy = false;
  bool _done = false;

  @override
  void dispose() {
    for (final controller in [_name, _email, _mobile, _password]) {
      controller.dispose();
    }
    super.dispose();
  }

  List<_Step> _steps(bool invited) => invited
      ? const [_Step.details, _Step.status]
      : const [_Step.details, _Step.church, _Step.group, _Step.status];

  void _go(bool invited, int offset) {
    final steps = _steps(invited);
    final index = (steps.indexOf(_step) + offset).clamp(0, steps.length - 1);
    setState(() {
      _formError = null;
      _step = steps[index];
    });
  }

  FieldKeys _validateDetails() => validateSignupDetails(
    name: _name.text,
    email: _email.text,
    mobileNumber: _mobile.text,
    password: _password.text,
  );

  void _next(bool invited) {
    final text = ref.read(appTextProvider);
    setState(() => _formError = null);
    if (_step == _Step.details) {
      final failed = _validateDetails();
      setState(() => _errors = failed);
      if (failed.isNotEmpty) return;
    }
    if (_step == _Step.church && _churchId == null) {
      return setState(() => _formError = text('signup.church.choose'));
    }
    if (_step == _Step.group && _groupId == null) {
      return setState(() => _formError = text('signup.group.choose'));
    }
    _go(invited, 1);
  }

  Future<void> _submit(bool invited) async {
    final failed = _validateDetails();
    if (failed.isNotEmpty) {
      setState(() {
        _errors = failed;
        _step = _Step.details;
      });
      return;
    }
    setState(() {
      _busy = true;
      _formError = null;
    });
    try {
      await ref
          .read(personRepositoryProvider)
          .signUp(
            fullName: _name.text.trim(),
            email: _email.text.trim(),
            mobileNumber: normaliseMobile(_mobile.text),
            password: _password.text,
            requestedStatus: _applied,
            homeGroupId: invited ? null : _groupId,
            invitationToken: invited ? widget.invitationToken : null,
          );
      if (mounted) setState(() => _done = true);
    } catch (error) {
      if (mounted) {
        setState(() => _formError = ref.read(appTextProvider).error(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _askForLink() async {
    final link = await showDialog<String>(
      context: context,
      builder: (context) => const _LinkDialog(),
    );
    final token = _tokenFrom(link ?? '');
    if (token != null && mounted) context.pushReplacement('/join/$token');
  }

  /// The token is the last part of a pasted link, or the whole text when only the token is given.
  static String? _tokenFrom(String pasted) {
    final trimmed = pasted.trim().split('?').first.split('#').first;
    final last = trimmed.split('/').where((p) => p.isNotEmpty).lastOrNull;
    return last == null || last.length < 10 ? null : last;
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final token = widget.invitationToken;
    final invitation = token == null
        ? null
        : ref.watch(invitationProvider(token));
    if (_done) return _Done(text: text);
    if (invitation != null && invitation.isLoading) {
      return AuthPage(
        title: text('member.signUp.title'),
        children: const [Center(child: CircularProgressIndicator())],
      );
    }
    final invited = invitation?.hasValue ?? false;
    final bad = invitation != null && invitation.hasError;
    final steps = _steps(invited);
    final index = steps.indexOf(_step);
    String? error(String field) {
      final key = _errors[field];
      return key == null ? null : text(key);
    }

    return AuthPage(
      title: text('member.signUp.title'),
      children: [
        Text(text('member.signUp.lead')),
        if (invited)
          MessageBanner(
            text('signup.invited', {
              'group': invitation!.requireValue.homeGroupName,
              'church': invitation.requireValue.churchName,
              'leader': invitation.requireValue.leaderName,
            }),
            kind: BannerKind.info,
          ),
        if (bad) ...[
          MessageBanner(text('signup.invitationBad')),
          TextButton(
            onPressed: () => context.pushReplacement('/sign-up'),
            child: Text(text('signup.chooseYourself')),
          ),
        ],
        Semantics(
          liveRegion: true,
          child: Text(
            text('signup.step', {
              'number': '${index + 1}',
              'total': '${steps.length}',
              'name': text('signup.step.${_step.name}'),
            }),
            style: Theme.of(context).textTheme.labelLarge,
          ),
        ),
        if (_formError != null) MessageBanner(_formError!),
        if (_step == _Step.details) ...[
          AppTextField(
            label: text('field.fullName'),
            controller: _name,
            error: error('full_name'),
            autofillHints: const [AutofillHints.name],
            capitalization: TextCapitalization.words,
          ),
          AppTextField(
            label: text('field.email'),
            controller: _email,
            error: error('email'),
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
          ),
          AppTextField(
            label: text('field.mobile'),
            controller: _mobile,
            error: error('mobile_number'),
            hint: text('field.mobileHint'),
            keyboardType: TextInputType.phone,
            autofillHints: const [AutofillHints.telephoneNumber],
          ),
          PasswordField(
            label: text('field.newPassword'),
            controller: _password,
            error: error('password'),
            hint: text('field.passwordHint'),
            showLabel: text('field.showPassword'),
            hideLabel: text('field.hidePassword'),
            autofillHints: const [AutofillHints.newPassword],
          ),
          if (token == null)
            TextButton(
              key: const Key('have-link'),
              onPressed: _askForLink,
              child: Text(text('member.signUp.haveLink')),
            ),
        ],
        if (_step == _Step.church) _churchChoice(text),
        if (_step == _Step.group) _groupChoice(text),
        if (_step == _Step.status) _statusChoice(text),
        // A Wrap, not a Row: at a large text size the buttons go onto two lines.
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          runSpacing: 8,
          children: [
            if (index > 0)
              TextButton(
                key: const Key('signup-back'),
                onPressed: _busy ? null : () => _go(invited, -1),
                child: Text(text('signup.back')),
              ),
            if (_step == _Step.status)
              FilledButton(
                key: const Key('signup-submit'),
                onPressed: _busy ? null : () => _submit(invited),
                child: Text(
                  _busy ? text('signup.working') : text('signup.submit'),
                ),
              )
            else
              FilledButton(
                key: const Key('signup-next'),
                onPressed: () => _next(invited),
                child: Text(text('signup.next')),
              ),
          ],
        ),
        Row(
          children: [
            Flexible(child: Text(text('member.signUp.haveAccount'))),
            TextButton(
              onPressed: () => context.pushReplacement('/sign-in'),
              child: Text(text('member.signIn.title')),
            ),
          ],
        ),
      ],
    );
  }

  Widget _churchChoice(AppText text) {
    return AsyncView<List<ChurchSummary>>(
      value: ref.watch(churchesProvider),
      onRetry: () => ref.invalidate(churchesProvider),
      builder: (churches) => churches.isEmpty
          ? Text(text('signup.none.church'))
          : RadioGroup<String>(
              groupValue: _churchId,
              onChanged: (value) => setState(() {
                _churchId = value;
                _groupId = null;
              }),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text('signup.church.choose'),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  for (final church in churches)
                    RadioListTile<String>(
                      key: Key('church-${church.id}'),
                      value: church.id,
                      title: Text(church.name),
                    ),
                ],
              ),
            ),
    );
  }

  Widget _groupChoice(AppText text) {
    final churchId = _churchId;
    if (churchId == null) return const SizedBox.shrink();
    return AsyncView<List<HomeGroupSummary>>(
      value: ref.watch(homeGroupsProvider(churchId)),
      onRetry: () => ref.invalidate(homeGroupsProvider(churchId)),
      builder: (groups) => groups.isEmpty
          ? Text(text('signup.none.group'))
          : RadioGroup<String>(
              groupValue: _groupId,
              onChanged: (value) => setState(() => _groupId = value),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text('signup.group.choose'),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  for (final group in groups)
                    RadioListTile<String>(
                      key: Key('group-${group.id}'),
                      value: group.id,
                      title: Text(group.name),
                      subtitle: Text(
                        text('signup.group.leader', {'name': group.leaderName}),
                      ),
                    ),
                ],
              ),
            ),
    );
  }

  Widget _statusChoice(AppText text) {
    return RadioGroup<String>(
      groupValue: _applied,
      onChanged: (value) => setState(() => _applied = value ?? _applied),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text('signup.apply.title'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          for (final status in const ['searcher', 'provider'])
            RadioListTile<String>(
              key: Key('apply-$status'),
              value: status,
              title: Text(text('signup.apply.$status')),
            ),
          Text(text('signup.apply.hint')),
        ],
      ),
    );
  }
}

class _Done extends StatelessWidget {
  const _Done({required this.text});

  final AppText text;

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      title: text('signup.done.title'),
      showBack: false,
      children: [
        MessageBanner(text('signup.done.text'), kind: BannerKind.success),
        FilledButton(
          key: const Key('go-sign-in'),
          onPressed: () => context.go('/sign-in'),
          child: Text(text('member.signIn.title')),
        ),
      ],
    );
  }
}

/// Asks for a pasted invitation link. It owns its controller, so the controller lives as long as
/// the dialog does, including while the dialog fades out.
class _LinkDialog extends ConsumerStatefulWidget {
  const _LinkDialog();

  @override
  ConsumerState<_LinkDialog> createState() => _LinkDialogState();
}

class _LinkDialogState extends ConsumerState<_LinkDialog> {
  final _link = TextEditingController();

  @override
  void dispose() {
    _link.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return AlertDialog(
      title: Text(text('member.signUp.haveLink')),
      content: TextField(
        controller: _link,
        autofocus: true,
        autocorrect: false,
        decoration: InputDecoration(labelText: text('member.signUp.linkLabel')),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(text('common.cancel')),
        ),
        FilledButton(
          key: const Key('use-link'),
          onPressed: () => Navigator.pop(context, _link.text),
          child: Text(text('member.signUp.linkUse')),
        ),
      ],
    );
  }
}
