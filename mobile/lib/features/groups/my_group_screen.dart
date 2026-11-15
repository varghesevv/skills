import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/providers.dart';
import '../../core/session/session_controller.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import '../person/leads.dart';
import '../person/person_providers.dart';
import '../person/person_router_paths.dart';

/// What a refused closing means. The server's code decides the words.
String _problem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'group_not_empty':
        return text('myGroup.error.notEmpty');
      case 'invalid_choice':
        return text('myGroup.error.choice');
      case 'state_changed':
        return text('leader.error.changed');
    }
  }
  return text.error(error);
}

/// The leader's own group: close it when they are its last member, by joining another one.
class MyGroupScreen extends ConsumerStatefulWidget {
  const MyGroupScreen({super.key});

  @override
  ConsumerState<MyGroupScreen> createState() => _MyGroupScreenState();
}

class _MyGroupScreenState extends ConsumerState<MyGroupScreen> {
  String _target = '';
  String _former = 'provider';
  bool _confirming = false;
  bool _busy = false;
  String? _error;
  final _warning = FocusNode();
  final _trigger = FocusNode();

  @override
  void dispose() {
    _warning.dispose();
    _trigger.dispose();
    super.dispose();
  }

  void _ask() {
    setState(() => _confirming = true);
    // The question replaces the button: move focus to it.
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _warning.requestFocus(),
    );
  }

  void _cancel() {
    setState(() => _confirming = false);
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _trigger.requestFocus(),
    );
  }

  Future<void> _close(String groupId, bool keeps) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final text = ref.read(appTextProvider);
    // The messenger belongs to the whole app, so the message survives the change of page: a
    // former VERIFIER no longer belongs on the leader pages, and the router sends them home.
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    try {
      final (closed, joined) = await ref
          .read(groupRepositoryProvider)
          .closeGroup(groupId, _target, keeps ? 'keep' : _former);
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            text('myGroup.close.done', {'closed': closed, 'joined': joined}),
          ),
        ),
      );
      router.go(personHome);
      await ref.read(sessionProvider.notifier).refreshPerson();
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = _problem(text, error);
          _confirming = false;
        });
        // The group or the target may be gone: ask for the list again, so it drops out.
        if (error is ApiException &&
            (error.code == 'state_changed' || error.code == 'not_found')) {
          final church = ref.read(personProvider)?.church.id;
          if (church != null) ref.invalidate(homeGroupsProvider(church));
        }
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final person = ref.watch(personProvider);
    final group = person?.homeGroup;
    if (person == null || group == null) return const SizedBox.shrink();
    // Only the leader of a group closes it. An ADMIN or the OWNER may belong to a group that
    // someone else leads, or have handed theirs on.
    if (!leadsOwnGroup(person)) {
      return Scaffold(
        appBar: AppBar(title: Text(text('myGroup.title'))),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(text('myGroup.notLeader')),
          ),
        ),
      );
    }
    final keeps = const {'admin', 'owner'}.contains(person.status.name);
    final groups = ref.watch(homeGroupsProvider(person.church.id));
    final name = {'group': group.name};
    return Scaffold(
      appBar: AppBar(title: Text(text('myGroup.title'))),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(text('myGroup.lead', name)),
            const SizedBox(height: 8),
            if (_error != null) MessageBanner(_error!),
            groups.when(
              loading: () => Center(
                child: Semantics(
                  label: text('config.loading'),
                  child: const CircularProgressIndicator(),
                ),
              ),
              error: (error, _) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  MessageBanner(text.error(error)),
                  FilledButton(
                    key: const Key('retry-groups'),
                    onPressed: () =>
                        ref.invalidate(homeGroupsProvider(person.church.id)),
                    child: Text(text('common.retry')),
                  ),
                ],
              ),
              data: (items) {
                final others = items.where((g) => g.id != group.id).toList();
                if (others.isEmpty) return Text(text('myGroup.close.none'));
                // A group that is no longer offered (closed meanwhile) cannot stay chosen.
                final target = others.any((g) => g.id == _target)
                    ? _target
                    : '';
                if (_confirming) {
                  return Semantics(
                    container: true,
                    label: text('myGroup.close.title', name),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Focus(
                          focusNode: _warning,
                          child: Text(text('myGroup.close.warning', name)),
                        ),
                        const SizedBox(height: 8),
                        FilledButton(
                          key: const Key('close-confirm'),
                          onPressed: _busy || target.isEmpty
                              ? null
                              : () => _close(group.id, keeps),
                          child: Text(text('myGroup.close.confirm')),
                        ),
                        TextButton(
                          key: const Key('close-cancel'),
                          onPressed: _busy ? null : _cancel,
                          child: Text(text('common.cancel')),
                        ),
                      ],
                    ),
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        text('myGroup.close.title', name),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      key: const Key('join'),
                      initialValue: target,
                      decoration: InputDecoration(
                        labelText: text('myGroup.close.to'),
                      ),
                      items: [
                        DropdownMenuItem(
                          value: '',
                          child: Text(text('myGroup.close.choose')),
                        ),
                        for (final g in others)
                          DropdownMenuItem(value: g.id, child: Text(g.name)),
                      ],
                      onChanged: (value) =>
                          setState(() => _target = value ?? ''),
                    ),
                    if (!keeps)
                      DropdownButtonFormField<String>(
                        isExpanded: true,
                        key: const Key('former'),
                        initialValue: _former,
                        decoration: InputDecoration(
                          labelText: text('myGroup.close.former'),
                        ),
                        items: [
                          for (final v in const ['provider', 'searcher'])
                            DropdownMenuItem(
                              value: v,
                              child: Text(text('admin.groups.former.$v')),
                            ),
                        ],
                        onChanged: (value) =>
                            setState(() => _former = value ?? 'provider'),
                      ),
                    const SizedBox(height: 8),
                    OutlinedButton(
                      key: const Key('close-open'),
                      focusNode: _trigger,
                      onPressed: _busy || target.isEmpty
                          ? null
                          : () {
                              setState(() => _target = target);
                              _ask();
                            },
                      child: Text(text('myGroup.close.submit', name)),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
