import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/user_type.dart';
import '../../core/providers.dart';
import 'auth_widgets.dart';

class WelcomeScreen extends ConsumerWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    return AuthPage(
      title: text('app.name'),
      showBack: false,
      children: [
        Text(
          text('landing.title'),
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        Text(text('landing.lead')),
        for (final type in UserType.values)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text('landing.${type.wire}.title'),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(text('landing.${type.wire}.text')),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      FilledButton(
                        key: Key('login-${type.wire}'),
                        onPressed: () => context.push('/login/${type.wire}'),
                        child: Text(text('nav.logIn')),
                      ),
                      OutlinedButton(
                        key: Key('register-${type.wire}'),
                        onPressed: () => context.push('/register/${type.wire}'),
                        child: Text(text('nav.register')),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
