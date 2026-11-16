import 'dart:math';

import 'package:flutter/foundation.dart';

import 'data/chat_models.dart';
import 'data/chat_repository.dart';

/// The longest message the server accepts.
const chatMaxChars = 2000;

/// A message that has been typed but not yet stored by the server.
class PendingMessage {
  PendingMessage(this.clientMessageId, this.body);

  /// Chosen here; sending it again after a lost answer stores the message once.
  final String clientMessageId;
  final String body;
  Object? error;

  bool get failed => error != null;
}

/// A random version 4 id, for [PendingMessage.clientMessageId].
String newClientMessageId([Random? random]) {
  final r = random ?? Random.secure();
  final bytes = List<int>.generate(16, (_) => r.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  String hex(int from, int to) => [
    for (final b in bytes.sublist(from, to))
      b.toRadixString(16).padLeft(2, '0'),
  ].join();
  return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
}

/// One conversation as the thread screen shows it: the messages loaded so far (newest first),
/// those being sent, and what is needed to page back and to mark messages read.
class ThreadModel extends ChangeNotifier {
  ThreadModel(this.id, this._repository, this.mySide, {this.onReadChanged});

  final String id;
  final ChatRepository _repository;
  final ChatSide mySide;

  /// Called after the server accepted a read mark (the list and the badge are then stale).
  final VoidCallback? onReadChanged;

  final List<ChatMessage> messages = [];
  final List<PendingMessage> pending = [];
  bool loading = true;
  bool hasMore = false;
  bool loadingOlder = false;
  Object? error;

  /// Why the older messages could not be loaded (the newer ones stay on screen).
  Object? olderError;
  bool _disposed = false;
  int _readUpTo = 0;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    loading = true;
    error = null;
    _changed();
    try {
      final page = await _repository.messages(id);
      messages
        ..clear()
        ..addAll(page);
      hasMore = page.length >= 50;
      error = null;
      await _markRead();
    } catch (e) {
      error = e;
    }
    loading = false;
    _changed();
  }

  Future<void> loadOlder() async {
    if (loadingOlder || !hasMore || messages.isEmpty) return;
    loadingOlder = true;
    olderError = null;
    _changed();
    try {
      final page = await _repository.messages(id, beforeSeq: messages.last.seq);
      for (final message in page) {
        _insert(message);
      }
      hasMore = page.length >= 50;
    } catch (e) {
      olderError = e;
    }
    loadingOlder = false;
    _changed();
  }

  /// Puts a message in its place unless it is already there (the answer of a send and the
  /// socket's copy of the same message arrive both).
  void _insert(ChatMessage message) {
    if (messages.any((m) => m.id == message.id)) return;
    final at = messages.indexWhere((m) => m.seq < message.seq);
    messages.insert(at == -1 ? messages.length : at, message);
  }

  /// A message that arrived by another way than a REST answer (the socket, S8.8).
  void receive(ChatMessage message) {
    if (message.conversationId != id) return;
    _insert(message);
    _changed();
    _markRead();
  }

  /// Sends [text] (trimmed); false when there is nothing to send. A failure stays in the list
  /// as a message that can be sent again with the same id.
  bool send(String text) {
    final body = text.trim();
    if (body.isEmpty || body.length > chatMaxChars) return false;
    final item = PendingMessage(newClientMessageId(), body);
    pending.add(item);
    _changed();
    _deliver(item);
    return true;
  }

  void retry(PendingMessage item) {
    if (!item.failed) return;
    item.error = null;
    _changed();
    _deliver(item);
  }

  void discard(PendingMessage item) {
    pending.remove(item);
    _changed();
  }

  Future<void> _deliver(PendingMessage item) async {
    try {
      final stored = await _repository.send(
        id,
        clientMessageId: item.clientMessageId,
        body: item.body,
      );
      pending.remove(item);
      _insert(stored);
    } catch (e) {
      item.error = e;
    }
    _changed();
  }

  Future<void> _markRead() async {
    final newest = messages.where((m) => m.senderSide != mySide).firstOrNull;
    if (newest == null || newest.seq <= _readUpTo) return;
    try {
      await _repository.markRead(id, newest.seq);
      _readUpTo = newest.seq;
      onReadChanged?.call();
    } catch (_) {
      // The next load tries again; a read mark is never worth an error on screen.
    }
  }
}
