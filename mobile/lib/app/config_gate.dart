import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api/api_exception.dart';
import '../core/errors/error_messages.dart';
import '../core/providers.dart';
import '../core/strings/app_text.dart';
import '../core/strings/bootstrap_strings.dart';
import '../core/terminology/terms.dart';

/// Keeps every screen behind the server's configuration. There is no built-in copy of the role
/// words, so nothing that names a role is shown until the config has loaded. Offers "try again"
/// when it cannot be reached, and blocks the app when the server asks for a newer version.
class ConfigGate extends ConsumerWidget {
  const ConfigGate({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(appConfigProvider);
    final version = ref.watch(appVersionProvider);
    return config.when(
      data: (data) {
        if (version.isNotEmpty && data.requiresUpdate(version)) {
          return _Notice(
            title: AppText(data.terms)('update.title'),
            message: AppText(data.terms)('update.text'),
          );
        }
        return child;
      },
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (error, _) => _Notice(
        title: BootstrapStrings.appName,
        // No words are known yet, so the neutral (empty) terms are used for the message.
        message: startupMessage(error),
        retryLabel: BootstrapStrings.tryAgain,
        onRetry: () => ref.invalidate(appConfigProvider),
      ),
    );
  }
}

/// The text shown when the server's configuration cannot be loaded at start-up.
///
/// A `404` means the server has no `GET /app/config` (it runs an older version than this app
/// needs), **or** the app points at the wrong address: a proxy or another site answers 404 too,
/// and the app cannot tell them apart from here. An answer of the wrong shape is the same kind of
/// mismatch. Saying "that item no longer exists" there would send the person looking for the wrong
/// problem, so the text names both causes. Other failures keep their own messages.
@visibleForTesting
String startupMessage(Object error) {
  if (error is ApiException &&
      (error.status == 404 || error.code == 'bad_response')) {
    return BootstrapStrings.serverMismatch;
  }
  return messageFor(error, const Terms({}));
}

class _Notice extends StatelessWidget {
  const _Notice({
    required this.title,
    required this.message,
    this.retryLabel,
    this.onRetry,
  });

  final String title;
  final String message;
  final String? retryLabel;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(message, textAlign: TextAlign.center),
                if (onRetry != null) ...[
                  const SizedBox(height: 16),
                  FilledButton(onPressed: onRetry, child: Text(retryLabel!)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
