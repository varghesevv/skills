import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/strings/app_text.dart';
import '../../shared/widgets/message_banner.dart';
import 'chat_list_screen.dart' show chatOtherName;
import 'chat_providers.dart';
import 'live/chat_events.dart';
import 'live/chat_live.dart';
import 'push/push_registration.dart';
import 'data/chat_models.dart';
import 'thread_model.dart';

/// One conversation: the messages (newest at the bottom), a box to write in, and the menu to
/// mute, block or report. Everything is sent and read through REST; the socket (S8.8) only
/// brings new messages sooner.
class ThreadScreen extends ConsumerWidget {
  const ThreadScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = ref.watch(appTextProvider);
    final one = ref.watch(conversationProvider(id));
    return one.when(
      loading: () => Scaffold(
        appBar: AppBar(title: Text(text('chat.title'))),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Scaffold(
        appBar: AppBar(title: Text(text('chat.title'))),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // A conversation that is not the person's (or does not exist) never appears by
              // trying again; any other failure may.
              if (error is ApiException && error.code == 'not_found')
                Text(text('chat.notFound'))
              else ...[
                MessageBanner(text.error(error)),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerLeft,
                  child: FilledButton(
                    onPressed: () => ref.invalidate(conversationProvider(id)),
                    child: Text(text('common.retry')),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      data: (found) => _Thread(key: ValueKey(id), conversation: found),
    );
  }
}

class _Thread extends ConsumerStatefulWidget {
  const _Thread({super.key, required this.conversation});

  final Conversation conversation;

  @override
  ConsumerState<_Thread> createState() => _ThreadState();
}

class _ThreadState extends ConsumerState<_Thread> {
  late final ThreadModel _model;
  final _input = TextEditingController();
  late Conversation _conversation = widget.conversation;
  StreamSubscription<ChatEvent>? _live;
  String? _menuError;

  @override
  void initState() {
    super.initState();
    _model = ThreadModel(
      _conversation.id,
      ref.read(chatRepositoryProvider),
      _conversation.mySide,
      onReadChanged: () {
        ref.invalidate(conversationsProvider);
        ref.invalidate(unreadMessagesProvider);
      },
    )..addListener(() => mounted ? setState(() {}) : null);
    _model.load();
    // News from the socket: a message of this conversation is added at once, and after a
    // reconnect the messages are read again, so nothing missed while away is lost.
    _live = ref.read(chatSocketProvider).events.listen((event) {
      switch (event) {
        case ChatMessageEvent(:final message):
          if (message.conversationId == _conversation.id &&
              _model.receive(message) &&
              message.senderSide != _conversation.mySide) {
            _announce(message);
          }
        case ChatConnected(:final again):
          if (again) _model.load();
        case ChatMarkEvent() || ChatDisconnected() || ChatErrorEvent():
          break;
      }
    });
  }

  /// A screen reader says a message that arrives while the thread is open (a sighted person
  /// sees it appear; this is what TalkBack needs instead).
  void _announce(ChatMessage message) {
    if (!mounted) return;
    final text = ref.read(appTextProvider);
    unawaited(
      SemanticsService.sendAnnouncement(
        View.of(context),
        text('chat.announce', {
          'name': chatOtherName(text, _conversation),
          'text': message.body,
        }),
        Directionality.of(context),
      ),
    );
  }

  /// The list is asked again every minute and after a read mark: take what it says now, so a
  /// mute or block made on another phone, or an account that was closed, shows here too.
  void _follow(
    AsyncValue<List<Conversation>>? _,
    AsyncValue<List<Conversation>> next,
  ) {
    final fresh = next.value
        ?.where((c) => c.id == _conversation.id)
        .firstOrNull;
    if (fresh != null && mounted) setState(() => _conversation = fresh);
  }

  @override
  void dispose() {
    unawaited(_live?.cancel());
    _model.dispose();
    _input.dispose();
    super.dispose();
  }

  void _send() {
    if (_model.send(_input.text)) _input.clear();
  }

  Future<void> _settings({bool? muted, bool? blocked}) async {
    setState(() => _menuError = null);
    try {
      final updated = await ref
          .read(chatRepositoryProvider)
          .settings(_conversation.id, muted: muted, blocked: blocked);
      if (!mounted) return;
      setState(() => _conversation = updated);
      ref.invalidate(conversationsProvider);
    } catch (error) {
      if (mounted) {
        setState(() => _menuError = ref.read(appTextProvider).error(error));
      }
    }
  }

  Future<void> _report() async {
    final text = ref.read(appTextProvider);
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: Text(text('chat.reportTitle')),
        children: [
          for (final code in chatReportReasons)
            SimpleDialogOption(
              key: Key('report-$code'),
              onPressed: () => Navigator.of(context).pop(code),
              child: Text(text('chat.reason.$code')),
            ),
        ],
      ),
    );
    if (reason == null || !mounted) return;
    setState(() => _menuError = null);
    try {
      await ref.read(chatRepositoryProvider).report(_conversation.id, reason);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(text('chat.reported'))));
    } catch (error) {
      if (mounted) setState(() => _menuError = text.error(error));
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(conversationsProvider, _follow);
    ref.watch(pushOfferProvider); // asks once whether to allow notifications
    final text = ref.watch(appTextProvider);
    final c = _conversation;
    final isProviderSide = c.mySide == ChatSide.provider;
    final canWrite = !c.otherClosed && !c.blocked;
    return Scaffold(
      appBar: AppBar(
        title: Text(chatOtherName(text, c)),
        actions: [
          PopupMenuButton<String>(
            key: const Key('chat-menu'),
            tooltip: text('chat.menu'),
            onSelected: (value) => switch (value) {
              'mute' => _settings(muted: !c.muted),
              'block' => _settings(blocked: !c.blocked),
              _ => _report(),
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                key: const Key('menu-mute'),
                value: 'mute',
                child: Text(text(c.muted ? 'chat.unmute' : 'chat.mute')),
              ),
              if (isProviderSide)
                PopupMenuItem(
                  key: const Key('menu-block'),
                  value: 'block',
                  child: Text(text(c.blocked ? 'chat.unblock' : 'chat.block')),
                ),
              PopupMenuItem(
                key: const Key('menu-report'),
                value: 'report',
                child: Text(text('chat.report')),
              ),
            ],
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_menuError != null)
              Padding(
                padding: const EdgeInsets.all(8),
                child: MessageBanner(_menuError!),
              ),
            Expanded(child: _messages(text)),
            if (!canWrite)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  text(
                    c.blocked ? 'chat.youBlocked' : 'chat.closedCannotWrite',
                  ),
                ),
              )
            else
              _Composer(
                controller: _input,
                onSend: _send,
                label: text('chat.write'),
                sendLabel: text('chat.send'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _messages(AppText text) {
    if (_model.loading && _model.messages.isEmpty) {
      return Center(
        child: Semantics(
          label: text('config.loading'),
          child: const CircularProgressIndicator(),
        ),
      );
    }
    if (_model.error != null && _model.messages.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          MessageBanner(text.error(_model.error!)),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: _model.load,
              child: Text(text('common.retry')),
            ),
          ),
        ],
      );
    }
    final mine = _conversation.mySide;
    final pending = _model.pending.reversed.toList();
    final messages = _model.messages;
    final older = _model.hasMore ? 1 : 0;
    final olderError = _model.olderError != null ? 1 : 0;
    final count = pending.length + messages.length + older + olderError;
    if (count == 0) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Text(text('chat.emptyThread')),
      );
    }
    // Reversed, so the first item is the newest, at the bottom. Rows are built as they scroll
    // into view: a long conversation costs what is on the screen, not its length.
    return ListView.builder(
      reverse: true,
      padding: const EdgeInsets.all(12),
      itemCount: count,
      itemBuilder: (context, index) {
        if (index < pending.length) {
          return _PendingBubble(
            item: pending[index],
            model: _model,
            text: text,
          );
        }
        index -= pending.length;
        if (index < messages.length) {
          final message = messages[index];
          return _Bubble(
            key: ValueKey(message.id),
            message: message,
            mine: message.senderSide == mine,
            text: text,
          );
        }
        index -= messages.length;
        if (index < older) {
          return Center(
            child: TextButton(
              key: const Key('older'),
              onPressed: _model.loadingOlder ? null : _model.loadOlder,
              child: Text(text('chat.older')),
            ),
          );
        }
        return MessageBanner(text.error(_model.olderError!));
      },
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.onSend,
    required this.label,
    required this.sendLabel,
  });

  final TextEditingController controller;
  final VoidCallback onSend;
  final String label;
  final String sendLabel;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(12, 4, 4, 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: TextField(
            key: const Key('message-input'),
            controller: controller,
            minLines: 1,
            maxLines: 5,
            maxLength: chatMaxChars,
            textCapitalization: TextCapitalization.sentences,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(labelText: label, counterText: ''),
          ),
        ),
        IconButton(
          key: const Key('send'),
          tooltip: sendLabel,
          icon: const Icon(Icons.send),
          onPressed: onSend,
        ),
      ],
    ),
  );
}

class _Bubble extends StatelessWidget {
  const _Bubble({
    super.key,
    required this.message,
    required this.mine,
    required this.text,
  });

  final ChatMessage message;
  final bool mine;
  final AppText text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final when = formatPeriodTime(message.createdAt);
    return Semantics(
      container: true,
      label: text(mine ? 'chat.sentBy.me' : 'chat.sentBy.other', {
        'text': message.body,
        'time': when,
      }),
      excludeSemantics: true,
      child: Align(
        alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.8,
          ),
          margin: const EdgeInsets.symmetric(vertical: 3),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: mine ? scheme.primaryContainer : scheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                message.body,
                style: TextStyle(
                  color: mine ? scheme.onPrimaryContainer : scheme.onSurface,
                ),
              ),
              Text(when, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _PendingBubble extends StatelessWidget {
  const _PendingBubble({
    required this.item,
    required this.model,
    required this.text,
  });

  final PendingMessage item;
  final ThreadModel model;
  final AppText text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.8,
        ),
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          border: Border.all(
            color: item.failed ? scheme.error : scheme.outlineVariant,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(item.body),
            if (!item.failed)
              Text(
                text('chat.sending'),
                style: Theme.of(context).textTheme.bodySmall,
              )
            else ...[
              Text(
                text.error(item.error!),
                style: TextStyle(color: scheme.error),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextButton(
                    key: const Key('retry-send'),
                    onPressed: () => model.retry(item),
                    child: Text(text('chat.retry')),
                  ),
                  TextButton(
                    key: const Key('discard-send'),
                    onPressed: () => model.discard(item),
                    child: Text(text('chat.discard')),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
