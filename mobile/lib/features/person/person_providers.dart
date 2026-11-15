import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'data/person_repository.dart';
import 'data/vouching_models.dart';

/// The open churches, for the sign-up wizard and the change of choice. Public (no login).
final churchesProvider = FutureProvider.autoDispose<List<ChurchSummary>>((ref) {
  return ref.watch(personRepositoryProvider).churches();
});

/// The open home groups of one church, each with its leader's name.
final homeGroupsProvider = FutureProvider.autoDispose
    .family<List<HomeGroupSummary>, String>((ref, churchId) {
      return ref.watch(personRepositoryProvider).homeGroups(churchId);
    });

/// What an invitation link leads to. Fails (the same way) for every kind of bad link.
final invitationProvider = FutureProvider.autoDispose
    .family<InvitationInfo, String>((ref, token) {
      return ref.watch(personRepositoryProvider).lookupInvitation(token);
    });

/// Whether the applicant has a vouch link that works (the link itself is shown once, when made).
final vouchLinkStateProvider = FutureProvider.autoDispose<VouchLinkState>((
  ref,
) {
  return ref.watch(personRepositoryProvider).vouchLinkState();
});

final vouchesReceivedProvider = FutureProvider.autoDispose<List<VouchReceived>>(
  (ref) {
    return ref.watch(personRepositoryProvider).vouchesReceived();
  },
);

final vouchesGivenProvider = FutureProvider.autoDispose<List<VouchGiven>>((
  ref,
) {
  return ref.watch(personRepositoryProvider).vouchesGiven();
});

/// How often a screen that is open asks for new notifications (decision D-18).
const notificationsPollInterval = Duration(seconds: 60);

/// The notifications, asked for again every minute while something watches this. A revoked
/// person has no access, so nothing here asks for them (the screens do not watch it).
final notificationsProvider = FutureProvider.autoDispose<NotificationList>((
  ref,
) {
  final timer = Timer(notificationsPollInterval, ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  return ref.watch(personRepositoryProvider).notifications();
});
