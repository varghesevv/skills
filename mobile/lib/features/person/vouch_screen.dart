import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/person_me.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/vouching_models.dart';
import 'person_providers.dart';
import 'person_router_paths.dart';

/// What a failed lookup or vouch means, by the code the server answers with.
String vouchProblem(AppText text, Object error, {String name = ''}) {
  if (error is ApiException) {
    switch (error.code) {
      case 'cannot_vouch_self':
        return text('vouch.page.self');
      case 'already_vouched':
        return name.isEmpty
            ? text('vouch.page.alreadyGeneric')
            : text('vouch.page.already', {'name': name});
      case 'not_found':
        return text('vouch.page.bad');
      case 'rate_limited':
        return text('vouch.page.limit');
      case 'not_admitted':
        return text('vouch.page.notAdmitted');
    }
  }
  return text.error(error);
}

/// The page a vouch link opens: who asks, and one button to vouch. The token is kept in this
/// screen only (not in a provider key) and travels in a request body.
class VouchScreen extends ConsumerStatefulWidget {
  const VouchScreen({super.key, required this.token});

  final String token;

  @override
  ConsumerState<VouchScreen> createState() => _VouchScreenState();
}

class _VouchScreenState extends ConsumerState<VouchScreen> {
  VouchLinkInfo? _info;
  Object? _lookupError;
  String? _vouchError;
  bool _busy = false;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    final person = ref.read(personProvider);
    if (_mayVouch(person)) _lookup();
  }

  static bool _mayVouch(PersonMe? person) =>
      person != null &&
      person.status != PersonStatus.pending &&
      person.status != PersonStatus.revoked;

  Future<void> _lookup() async {
    try {
      final info = await ref
          .read(personRepositoryProvider)
          .lookupVouchLink(widget.token);
      if (mounted) setState(() => _info = info);
    } catch (error) {
      if (mounted) setState(() => _lookupError = error);
    }
  }

  Future<void> _vouch() async {
    setState(() {
      _busy = true;
      _vouchError = null;
    });
    try {
      await ref.read(personRepositoryProvider).vouch(widget.token);
      if (!mounted) return;
      ref.invalidate(vouchesGivenProvider);
      setState(() => _done = true);
    } catch (error) {
      if (mounted) {
        setState(
          () => _vouchError = vouchProblem(
            ref.read(appTextProvider),
            error,
            name: _info?.applicantName ?? '',
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = ref.watch(personProvider);
    final info = _info;
    final Widget body;
    if (!_mayVouch(person)) {
      body = MessageBanner(
        person?.status == PersonStatus.revoked
            ? text('revoked.text')
            : text('vouch.page.notAdmitted'),
        kind: BannerKind.info,
      );
    } else if (_lookupError != null) {
      body = MessageBanner(vouchProblem(text, _lookupError!));
    } else if (info == null) {
      body = Center(
        child: Semantics(
          label: text('vouch.page.checking'),
          child: const CircularProgressIndicator(),
        ),
      );
    } else if (_done) {
      body = MessageBanner(
        text('vouch.page.done', {'name': info.applicantName}),
        kind: BannerKind.success,
      );
    } else if (info.alreadyVouched) {
      body = MessageBanner(
        text('vouch.page.already', {'name': info.applicantName}),
        kind: BannerKind.info,
      );
    } else {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text('vouch.page.text', {
              'name': info.applicantName,
              'church': info.churchName,
              'group': info.homeGroupName,
              'goal': text('vouch.page.goal.${info.requestedStatus}'),
            }),
          ),
          const SizedBox(height: 8),
          Text(text('vouch.page.warning')),
          if (_vouchError != null) ...[
            const SizedBox(height: 8),
            MessageBanner(_vouchError!),
          ],
          const SizedBox(height: 16),
          FilledButton(
            key: const Key('vouch-submit'),
            onPressed: _busy ? null : _vouch,
            child: Text(
              _busy
                  ? text('vouch.page.working')
                  : text('vouch.page.submit', {'name': info.applicantName}),
            ),
          ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(text('vouch.page.title')),
        leading: BackButton(onPressed: () => context.go(personHome)),
      ),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [body]),
      ),
    );
  }
}
