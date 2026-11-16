import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'data/chat_models.dart';
import 'data/chat_repository.dart';

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.watch(apiClientProvider));
});

/// How often an open screen asks again (the socket, when it is up, brings news sooner).
const chatPollInterval = Duration(seconds: 60);

/// The person's conversations, latest activity first (the first 50).
final conversationsProvider = FutureProvider.autoDispose<List<Conversation>>((
  ref,
) async {
  final timer = Timer(chatPollInterval, ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  final page = await ref.watch(chatRepositoryProvider).conversations();
  return page.items;
});

/// One conversation by its id, for the thread screen (it may be outside the first page of the
/// list, or opened from a push).
final conversationProvider = FutureProvider.autoDispose
    .family<Conversation, String>((ref, id) {
      return ref.watch(chatRepositoryProvider).conversation(id);
    });

/// Messages not yet read, over all conversations, for the badge.
final unreadMessagesProvider = FutureProvider.autoDispose<int>((ref) {
  final timer = Timer(chatPollInterval, ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  return ref.watch(chatRepositoryProvider).unread();
});
