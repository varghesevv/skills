import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/async_view.dart';
import '../../shared/widgets/message_banner.dart';
import 'data/vouching_models.dart';
import 'person_providers.dart';

/// One line for a notification, from its kind and the person it is about.
String notificationText(AppText text, NotificationItem item) {
  final name = item.subjectName.isEmpty
      ? text('notifications.someone')
      : item.subjectName;
  return switch (item.kind) {
    'applicant_new' => text('notifications.applicant_new', {'name': name}),
    'vouch_received' => text('notifications.vouch_received', {'name': name}),
    'admitted' => text('notifications.admitted', {'name': name}),
    _ => text('notifications.unknown'),
  };
}

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  String? _error;

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _error = null);
    try {
      await action();
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(appTextProvider).error(error));
      }
    } finally {
      ref.invalidate(notificationsProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    final list = ref.watch(notificationsProvider);
    final repository = ref.read(personRepositoryProvider);
    final hasUnread = (list.value?.unreadCount ?? 0) > 0;
    return Scaffold(
      appBar: AppBar(
        title: Text(text('notifications.title')),
        actions: [
          if (hasUnread)
            TextButton(
              key: const Key('read-all'),
              onPressed: () => _run(repository.markAllNotificationsRead),
              child: Text(text('notifications.readAll')),
            ),
        ],
      ),
      body: SafeArea(
        child: AsyncView<NotificationList>(
          value: list,
          onRetry: () => ref.invalidate(notificationsProvider),
          builder: (data) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_error != null) MessageBanner(_error!),
              if (data.items.isEmpty) Text(text('notifications.none')),
              for (final item in data.items)
                _Row(
                  item: item,
                  text: text,
                  onRead: () =>
                      _run(() => repository.markNotificationRead(item.id)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.item, required this.text, required this.onRead});

  final NotificationItem item;
  final AppText text;
  final VoidCallback onRead;

  @override
  Widget build(BuildContext context) {
    final line = notificationText(text, item);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            [
              if (!item.read) text('notifications.new'),
              line,
              formatPeriodTime(item.createdAt),
            ].join(' · '),
            style: item.read
                ? null
                : const TextStyle(fontWeight: FontWeight.bold),
          ),
          if (!item.read)
            TextButton(
              onPressed: onRead,
              child: Text(text('notifications.read', {'text': line})),
            ),
        ],
      ),
    );
  }
}
