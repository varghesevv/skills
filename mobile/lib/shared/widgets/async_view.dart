import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/errors/error_messages.dart';
import '../../core/providers.dart';
import 'message_banner.dart';

/// Shows the loading, error (with "try again") and content states of a loaded value, so every
/// screen handles all three the same way.
class AsyncView<T> extends ConsumerWidget {
  const AsyncView({
    super.key,
    required this.value,
    required this.onRetry,
    required this.builder,
  });

  final AsyncValue<T> value;
  final VoidCallback onRetry;
  final Widget Function(T data) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    return value.when(
      // Reloading in the background (after a save) keeps the screen and what was typed.
      skipLoadingOnReload: true,
      data: builder,
      loading: () => Center(
        child: Semantics(
          label: text('config.loading'),
          child: const CircularProgressIndicator(),
        ),
      ),
      error: (error, _) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          MessageBanner(messageFor(error, ref.watch(termsProvider)!)),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: onRetry,
              child: Text(text('common.retry')),
            ),
          ),
        ],
      ),
    );
  }
}
