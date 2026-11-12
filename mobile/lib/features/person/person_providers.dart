import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'data/person_repository.dart';

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
