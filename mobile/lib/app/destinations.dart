import 'package:flutter/material.dart';

import '../core/auth/user_type.dart';
import '../features/freelancer/profile/profile_screen.dart';
import '../features/home/dashboard_screen.dart';
import '../features/settings/settings_screen.dart';

/// One tab of the bottom navigation.
class Destination {
  const Destination({
    required this.path,
    required this.labelKey,
    required this.icon,
    required this.selectedIcon,
    required this.builder,
  });

  final String path; // below the role prefix, for example `profile`
  final String labelKey; // key in `strings_en.dart`
  final IconData icon;
  final IconData selectedIcon;
  final Widget Function() builder;
}

final _home = Destination(
  path: 'home',
  labelKey: 'nav.home',
  icon: Icons.home_outlined,
  selectedIcon: Icons.home,
  builder: () => const DashboardScreen(),
);

final _settings = Destination(
  path: 'settings',
  labelKey: 'nav.settings',
  icon: Icons.settings_outlined,
  selectedIcon: Icons.settings,
  builder: () => const SettingsScreen(),
);

/// The tabs of each role. Each role's features are added here as they are built (phases 2 to 4).
List<Destination> destinationsFor(UserType type) => switch (type) {
  UserType.freelancer => [
    _home,
    Destination(
      path: 'profile',
      labelKey: 'nav.profile',
      icon: Icons.person_outline,
      selectedIcon: Icons.person,
      builder: () => const FreelancerProfileScreen(),
    ),
    _settings,
  ],
  UserType.workhost || UserType.organisation => [_home, _settings],
};
