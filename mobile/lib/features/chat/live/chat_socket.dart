import 'dart:async';
import 'dart:convert';
import 'dart:math';

import '../data/chat_models.dart';
import 'chat_events.dart';
import 'chat_link.dart';

enum ChatSocketStatus {
  /// Not asked to run (signed out, or the app is in the background).
  stopped,
  connecting,
  connected,

  /// Lost; waiting to try again.
  waiting,

  /// The server said this person may not chat; nothing is tried again until restarted.
  denied,
}

/// The live connection to chat (docs/android/chat-design.md, section 5). It brings new messages
/// and read marks sooner than polling; everything it does can also be done over REST, so a
/// connection that is down costs only time.
///
/// - The access token goes in the first frame, never in the address.
/// - A ping every [heartbeat]; a connection silent for [idle] is dropped and reopened.
/// - Close `4401` (token expired): renew the session and reconnect at once. `4403`: stop.
///   `4429` (too many frames): wait longer. Anything else: try again after 1, 2, 4 ... 30 s.
class ChatSocket {
  ChatSocket({
    required this.address,
    required this.connector,
    required this.accessToken,
    required this.renewSession,
    Random? random,
    this.heartbeat = const Duration(seconds: 25),
    this.idle = const Duration(seconds: 70),
    this.readyWait = const Duration(seconds: 10),
    this.maxBackoff = const Duration(seconds: 30),
  }) : _random = random ?? Random();

  final Uri address;
  final ChatConnector connector;

  /// The current access token, or null when there is none (the app was restarted).
  final Future<String?> Function() accessToken;

  /// Renews the session; false when it could not be (then nothing is retried until restarted).
  final Future<bool> Function() renewSession;
  final Duration heartbeat;
  final Duration idle;
  final Duration readyWait;
  final Duration maxBackoff;
  final Random _random;

  final _events = StreamController<ChatEvent>.broadcast();
  ChatSocketStatus _status = ChatSocketStatus.stopped;
  ChatLink? _link;
  StreamSubscription<String>? _subscription;
  Timer? _retry;
  Timer? _pinger;
  Timer? _watchdog;
  Timer? _readyTimer;
  int _failures = 0;
  int _generation = 0;
  bool _connectedBefore = false;
  bool _renewedOnce = false;

  Stream<ChatEvent> get events => _events.stream;

  ChatSocketStatus get status => _status;

  /// Starts (or restarts) the connection. Safe to call when it is already running.
  void start() {
    if (_status == ChatSocketStatus.connecting ||
        _status == ChatSocketStatus.connected ||
        _status == ChatSocketStatus.waiting) {
      return;
    }
    _failures = 0;
    _open();
  }

  /// Closes the connection and stops trying (signed out, or the app went to the background).
  Future<void> stop() async {
    _generation++;
    _cancelTimers();
    _retry?.cancel();
    final link = _link;
    _link = null;
    final subscription = _subscription;
    _subscription = null;
    final was = _status;
    _status = ChatSocketStatus.stopped;
    if (was == ChatSocketStatus.connected) _emit(const ChatDisconnected());
    unawaited(subscription?.cancel());
    // Closing a connection that is already gone is not an error, and never worth waiting for.
    if (link != null) unawaited(link.close().catchError((Object _) {}));
  }

  Future<void> dispose() async {
    await stop();
    await _events.close();
  }

  /// The app received messages up to [upToSeq] (said at once, whether or not the thread is
  /// open). Dropped when there is no connection: REST read marks cover the rest.
  void delivered(String conversationId, int upToSeq) => _send({
    'type': 'delivered',
    'conversation_id': conversationId,
    'up_to_seq': upToSeq,
  });

  void _send(Map<String, Object?> frame) {
    if (_status != ChatSocketStatus.connected) return;
    _link?.send(jsonEncode(frame));
  }

  Future<void> _open() async {
    final generation = ++_generation;
    _status = ChatSocketStatus.connecting;
    try {
      var token = await accessToken();
      if (token == null) {
        if (!await renewSession()) return _giveUp(generation);
        token = await accessToken();
      }
      if (generation != _generation) return;
      if (token == null) return _lost(generation);
      // A network that never answers must not hold the socket in "connecting" for ever.
      final link = await connector(address).timeout(readyWait);
      if (generation != _generation) {
        await link.close();
        return;
      }
      _link = link;
      _subscription = link.frames.listen(
        (frame) => _onFrame(generation, frame),
        onDone: () => _onClosed(generation),
        onError: (_) => _onClosed(generation),
        cancelOnError: true,
      );
      link.send(jsonEncode({'type': 'auth', 'token': token}));
      _readyTimer = Timer(readyWait, () => _lost(generation));
    } catch (_) {
      if (generation == _generation) _lost(generation);
    }
  }

  void _giveUp(int generation) {
    if (generation != _generation) return;
    _status = ChatSocketStatus.stopped;
  }

  void _onFrame(int generation, String text) {
    if (generation != _generation) return;
    _resetWatchdog(generation);
    final Object? frame;
    try {
      frame = jsonDecode(text);
    } on FormatException {
      return;
    }
    if (frame is! Map) return;
    switch (frame['type']) {
      case 'ready':
        _readyTimer?.cancel();
        _status = ChatSocketStatus.connected;
        _failures = 0;
        _renewedOnce = false;
        _pinger?.cancel(); // a repeated ready must not leave a second timer running
        _pinger = Timer.periodic(heartbeat, (_) => _send({'type': 'ping'}));
        _resetWatchdog(generation);
        final again = _connectedBefore;
        _connectedBefore = true;
        _emit(ChatConnected(again: again));
      case 'message':
        final message = frame['message'];
        if (message is Map) {
          try {
            _emit(
              ChatMessageEvent(
                ChatMessage.fromJson(Map<String, Object?>.from(message)),
              ),
            );
          } on Object {
            // A frame of a shape this version does not know is skipped, never fatal.
          }
        }
      case 'read' || 'delivered':
        final side = frame['side'];
        final seq = frame['up_to_seq'];
        final id = frame['conversation_id'];
        if (id is String &&
            seq is int &&
            (side == 'starter' || side == 'provider')) {
          _emit(
            ChatMarkEvent(
              read: frame['type'] == 'read',
              conversationId: id,
              side: side == 'starter' ? ChatSide.starter : ChatSide.provider,
              upToSeq: seq,
            ),
          );
        }
      case 'error':
        final code = frame['code'];
        if (code is String) _emit(ChatErrorEvent(code));
    }
  }

  void _resetWatchdog(int generation) {
    _watchdog?.cancel();
    _watchdog = Timer(idle, () => _lost(generation));
  }

  void _onClosed(int generation) {
    if (generation != _generation) return;
    final code = _link?.closeCode;
    _link = null;
    switch (code) {
      case 4401:
        _renewAndReconnect(generation);
      case 4403:
        _stopFor(generation, ChatSocketStatus.denied);
      case 4429:
        _wait(generation, const Duration(seconds: 30));
      default:
        _lost(generation);
    }
  }

  /// The token ran out: renew the session once and reconnect at once. When that does not help
  /// (renewing failed, or the new token is refused too) fall back to waiting.
  Future<void> _renewAndReconnect(int generation) async {
    final wasConnected = _status == ChatSocketStatus.connected;
    _tearDown();
    _status = ChatSocketStatus.waiting;
    if (wasConnected) _emit(const ChatDisconnected());
    if (_renewedOnce) return _lost(generation);
    _renewedOnce = true;
    final bool renewed;
    try {
      renewed = await renewSession();
    } on Object {
      return _lost(generation);
    }
    if (generation != _generation) return;
    if (!renewed) return _giveUp(generation);
    _open();
  }

  void _stopFor(int generation, ChatSocketStatus status) {
    if (generation != _generation) return;
    _tearDown();
    _status = status;
  }

  /// The connection is lost or never came up: wait, then try again.
  void _lost(int generation) {
    if (generation != _generation) return;
    final delay = Duration(
      milliseconds:
          min(maxBackoff.inMilliseconds, 1000 * (1 << min(_failures, 5))) +
          _random.nextInt(1000),
    );
    _failures++;
    _wait(generation, delay);
  }

  void _wait(int generation, Duration delay) {
    if (generation != _generation) return;
    final wasConnected = _status == ChatSocketStatus.connected;
    _tearDown();
    _status = ChatSocketStatus.waiting;
    if (wasConnected) _emit(const ChatDisconnected());
    _retry = Timer(delay, () {
      if (generation == _generation && _status == ChatSocketStatus.waiting) {
        _open();
      }
    });
  }

  void _tearDown() {
    _cancelTimers();
    final link = _link;
    _link = null;
    unawaited(_subscription?.cancel());
    _subscription = null;
    if (link != null) {
      unawaited(link.close().catchError((Object _) {}));
    }
  }

  void _cancelTimers() {
    _pinger?.cancel();
    _watchdog?.cancel();
    _readyTimer?.cancel();
    _pinger = _watchdog = _readyTimer = null;
  }

  void _emit(ChatEvent event) {
    if (!_events.isClosed) _events.add(event);
  }
}
