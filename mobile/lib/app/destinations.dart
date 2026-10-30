import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/user_type.dart';
import '../features/freelancer/labels/labels_screen.dart';
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
    this.routes = const [],
  });

  final String path; // below the role prefix, for example `profile`
  final String labelKey; // key in `strings_en.dart`
  final IconData icon;
  final IconData selectedIcon;
  final Widget Function() builder;

  /// Screens opened from this tab. They keep the bottom bar and the tab's own stack.
  final List<RouteBase> routes;
}

/// A link on the dashboard to a screen of the person's role ("Where to go next").
class Shortcut {
  const Shortcut({
    required this.labelKey,
    required this.location,
    required this.icon,
  });

  final String labelKey;
  final String location;
  final IconData icon;
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
      routes: [
        GoRoute(
          path: 'labels',
          builder: (context, state) => const FreelancerLabelsScreen(),
        ),
      ],
    ),
    _settings,
  ],
  UserType.workhost || UserType.organisation => [_home, _settings],
};

/// The dashboard shortcuts of each role; the web dashboard links to the same pages.
List<Shortcut> shortcutsFor(UserType type) => switch (type) {
  UserType.freelancer => const [
    Shortcut(
      labelKey: 'nav.profile',
      location: '/freelancer/profile',
      icon: Icons.person_outline,
    ),
    Shortcut(
      labelKey: 'nav.labels',
      location: '/freelancer/profile/labels',
      icon: Icons.sell_outlined,
    ),
  ],
  UserType.workhost || UserType.organisation => const [],
};
