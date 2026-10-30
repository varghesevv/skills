import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'data/freelancer_profile.dart';
import 'data/freelancer_repository.dart';

final freelancerRepositoryProvider = Provider<FreelancerRepository>(
  (ref) => FreelancerRepository(ref.watch(apiClientProvider)),
);

/// The profile, loaded when the screen opens and dropped when it closes, so a person who logs in
/// as someone else never sees the previous profile.
final freelancerProfileProvider = FutureProvider.autoDispose<FreelancerProfile>(
  (ref) => ref.watch(freelancerRepositoryProvider).profile(),
);
