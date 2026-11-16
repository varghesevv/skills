import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/format.dart';
import '../../core/providers.dart';
import '../../shared/widgets/async_view.dart';
import 'chat_paths.dart';
import 'push/push_registration.dart';
import 'chat_providers.dart';
import 'data/chat_models.dart';

/// The person's conversations, latest first, with how many messages are unread.
class ChatListScreen extends ConsumerWidget {
  const ChatListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final list = ref.watch(conversationsProvider);
    ref.watch(pushOfferProvider); // asks once whether to allow notifications
    return Scaffold(
      appBar: AppBar(title: Text(text('chat.title'))),
      body: SafeArea(
        child: AsyncView<List<Conversation>>(
          value: list,
          onRetry: () => ref.invalidate(conversationsProvider),
          builder: (items) => RefreshIndicator(
            onRefresh: () async => ref.refresh(conversationsProvider.future),
            child: items.isEmpty
                ? ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [Text(text('chat.none'))],
                  )
                : ListView.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (context, index) => _Row(item: items[index]),
                  ),
          ),
        ),
      ),
    );
  }
}

/// The name shown for the other person; a closed account has none.
String chatOtherName(dynamic text, Conversation item) =>
    (item.otherName == null || item.otherName!.isEmpty)
    ? text('chat.closedAccount') as String
    : item.otherName!;

class _Row extends ConsumerWidget {
  const _Row({required this.item});

  final Conversation item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final name = chatOtherName(text, item);
    final when = item.lastMessageAt;
    final unread = item.unread > 0;
    return ListTile(
      key: Key('conversation-${item.id}'),
      title: Text(
        name,
        // A screen reader hears the name with what is new, before the preview.
        semanticsLabel: [
          name,
          if (unread) text('chat.unreadCount', {'count': '${item.unread}'}),
          if (item.muted) text('chat.muted'),
        ].join(', '),
        style: unread ? const TextStyle(fontWeight: FontWeight.bold) : null,
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (item.preview != null)
            Text(item.preview!, maxLines: 2, overflow: TextOverflow.ellipsis),
          if (when != null)
            Text(formatDay(when), style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
      trailing: unread ? Badge(label: Text('${item.unread}')) : null,
      onTap: () => context.push(chatThread(item.id)),
    );
  }
}
