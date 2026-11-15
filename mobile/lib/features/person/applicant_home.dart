import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/person_me.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/person_repository.dart';
import 'leave_account.dart';
import 'person_providers.dart';
import 'vouch_share.dart';

const _keep = '';

/// A person waiting to be admitted: where they applied, the vouches so far, change or leave.
class ApplicantHome extends ConsumerStatefulWidget {
  const ApplicantHome({super.key, required this.person});

  final PersonMe person;

  @override
  ConsumerState<ApplicantHome> createState() => _ApplicantHomeState();
}

class _ApplicantHomeState extends ConsumerState<ApplicantHome> {
  bool _saved = false;

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = widget.person;
    final appliedFor = person.requestedStatus ?? 'searcher';
    Widget fact(String label, String? value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Semantics(
        container: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            Text(value ?? '', style: Theme.of(context).textTheme.bodyLarge),
          ],
        ),
      ),
    );
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(text('applicant.lead')),
        const SizedBox(height: 8),
        fact(text('applicant.church'), person.church.name),
        fact(text('applicant.group'), person.homeGroup?.name),
        fact(text('applicant.leader'), person.leaderName),
        fact(
          text('applicant.applyingFor'),
          text('applicant.applyingFor.$appliedFor'),
        ),
        fact(
          text('applicant.vouches'),
          person.vouchCount == 1
              ? text('applicant.vouchCount.one')
              : text('applicant.vouchCount', {'count': '${person.vouchCount}'}),
        ),
        Text(text('applicant.vouchesHelp')),
        const Divider(height: 32),
        const VouchShare(),
        const Divider(height: 32),
        _ChangeChoice(
          key: ValueKey('${person.homeGroup?.id}-${person.requestedStatus}'),
          person: person,
          saved: _saved,
          onStart: () => setState(() => _saved = false),
          onSaved: (updated) {
            if (!mounted) return;
            ref.read(sessionProvider.notifier).setPerson(updated);
            setState(() => _saved = true);
          },
        ),
        const Divider(height: 32),
        const LeaveAccount(),
      ],
    );
  }
}

class _ChangeChoice extends ConsumerStatefulWidget {
  const _ChangeChoice({
    super.key,
    required this.person,
    required this.saved,
    required this.onStart,
    required this.onSaved,
  });

  final PersonMe person;
  final bool saved;
  final VoidCallback onStart;
  final void Function(PersonMe updated) onSaved;

  @override
  ConsumerState<_ChangeChoice> createState() => _ChangeChoiceState();
}

class _ChangeChoiceState extends ConsumerState<_ChangeChoice> {
  late String _churchId = widget.person.church.id;
  String _groupId = _keep;
  late String _applied = widget.person.requestedStatus ?? 'searcher';
  String? _formError;
  bool _busy = false;

  Future<void> _save() async {
    setState(() {
      _formError = null;
      _busy = true;
    });
    widget.onStart();
    try {
      final updated = await ref
          .read(personRepositoryProvider)
          .updateApplication(
            homeGroupId: _groupId == _keep ? null : _groupId,
            requestedStatus: _applied,
          );
      if (!mounted) return;
      widget.onSaved(updated);
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
    final person = widget.person;
    final churches = ref.watch(churchesProvider);
    final groups = ref.watch(homeGroupsProvider(_churchId));
    final sameChurch = _churchId == person.church.id;
    final otherGroups = [
      for (final group in groups.value ?? const <HomeGroupSummary>[])
        if (group.id != person.homeGroup?.id) group,
    ];
    final loaded = churches.hasValue && groups.hasValue;
    final unchanged = _groupId == _keep && _applied == person.requestedStatus;
    final canSave =
        !_busy && loaded && !unchanged && (sameChurch || _groupId != _keep);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          text('applicant.change.title'),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 12),
        if (_formError != null) MessageBanner(_formError!),
        if (widget.saved)
          MessageBanner(
            text('applicant.change.saved'),
            kind: BannerKind.success,
          ),
        if (churches.isLoading || groups.isLoading)
          const Center(child: CircularProgressIndicator()),
        if (churches.hasError) ...[
          MessageBanner(text.error(churches.error!)),
          TextButton(
            onPressed: () => ref.invalidate(churchesProvider),
            child: Text(text('common.retry')),
          ),
        ],
        if (groups.hasError) ...[
          MessageBanner(text.error(groups.error!)),
          TextButton(
            onPressed: () => ref.invalidate(homeGroupsProvider(_churchId)),
            child: Text(text('common.retry')),
          ),
        ],
        if (groups.hasValue && otherGroups.isEmpty && !sameChurch)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(text('signup.none.group')),
          ),
        DropdownButtonFormField<String>(
          key: const Key('change-church'),
          initialValue: _churchId,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: text('applicant.change.church'),
          ),
          items: [
            for (final church in churches.value ?? const <ChurchSummary>[])
              DropdownMenuItem(value: church.id, child: Text(church.name)),
          ],
          onChanged: (value) => setState(() {
            _churchId = value ?? _churchId;
            _groupId = _keep;
          }),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey('change-group-$_churchId'),
          initialValue: _groupId,
          isExpanded: true,
          decoration: InputDecoration(labelText: text('applicant.group')),
          items: [
            DropdownMenuItem(
              value: _keep,
              child: Text(
                sameChurch
                    ? text('applicant.change.keep')
                    : text('signup.group.choose'),
              ),
            ),
            for (final group in otherGroups)
              DropdownMenuItem(
                value: group.id,
                child: Text(
                  '${group.name} (${text('signup.group.leader', {'name': group.leaderName})})',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: (value) => setState(() => _groupId = value ?? _keep),
        ),
        const SizedBox(height: 12),
        RadioGroup<String>(
          groupValue: _applied,
          onChanged: (value) => setState(() => _applied = value ?? _applied),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                text('signup.apply.title'),
                style: Theme.of(context).textTheme.labelLarge,
              ),
              for (final status in const ['searcher', 'provider'])
                RadioListTile<String>(
                  key: Key('change-apply-$status'),
                  value: status,
                  title: Text(text('signup.apply.$status')),
                ),
            ],
          ),
        ),
        FilledButton(
          key: const Key('change-save'),
          onPressed: canSave ? _save : null,
          child: Text(text('applicant.change.save')),
        ),
      ],
    );
  }
}
