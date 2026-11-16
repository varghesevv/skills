import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/env.dart';
import '../../../core/providers.dart';
import '../chat_providers.dart';
import 'chat_events.dart';
import 'chat_link.dart';
import 'chat_socket.dart';

/// The address of the chat socket for an API address: `https://host/api/v1` gives
/// `wss://host/api/v1/chat/ws`. A plain `http` address (a local server) gives `ws`.
Uri chatSocketUri(String apiBase) {
  final base = apiBase.endsWith('/')
      ? apiBase.substring(0, apiBase.length - 1)
      : apiBase;
  final secure = base.startsWith('https://');
  final rest = base.replaceFirst(RegExp(r'^https?://'), '');
  return Uri.parse('${secure ? 'wss' : 'ws'}://$rest/chat/ws');
}

/// How a connection is opened. A provider so that tests can replace the network.
final chatConnectorProvider = Provider<ChatConnector>(
  (ref) => connectWebSocket,
);

final chatSocketProvider = Provider<ChatSocket>((ref) {
  final tokens = ref.watch(tokenStoreProvider);
  final api = ref.watch(apiClientProvider);
  final socket = ChatSocket(
    address: chatSocketUri(Env.apiBaseUrl),
    connector: ref.watch(chatConnectorProvider),
    accessToken: () async => tokens.accessToken,
    renewSession: api.refreshSession,
  );
  ref.onDispose(socket.dispose);
  return socket;
});

/// Keeps the socket up while a member who may chat has the app open, and turns what it says
/// into fresh lists and badges. Watched by the member's home page, so it lives exactly as long
/// as the sign-in does and ends with it. The socket is closed when the app goes to the
/// background (a phone should not keep a connection open for nobody) and opened again when it
/// returns; whatever came meanwhile is read over REST.
final chatLiveProvider = Provider.autoDispose<void>((ref) {
  final socket = ref.watch(chatSocketProvider);
  final listener = AppLifecycleListener(
    onStateChange: (state) {
      switch (state) {
        case AppLifecycleState.resumed:
          socket.start();
        case AppLifecycleState.hidden ||
            AppLifecycleState.paused ||
            AppLifecycleState.detached:
          unawaited(socket.stop());
        case AppLifecycleState.inactive:
          break; // a dialog or a split screen: still on show
      }
    },
  );
  final current = WidgetsBinding.instance.lifecycleState;
  if (current == null || current == AppLifecycleState.resumed) socket.start();

  void refresh() {
    ref.invalidate(conversationsProvider);
    ref.invalidate(unreadMessagesProvider);
  }

  final events = socket.events.listen((event) {
    switch (event) {
      case ChatMessageEvent(:final message):
        // Said at once so that no push follows for what the phone already has.
        socket.delivered(message.conversationId, message.seq);
        refresh();
      case ChatConnected(:final again):
        if (again) refresh();
      case ChatMarkEvent() || ChatDisconnected() || ChatErrorEvent():
        break;
    }
  });
  ref.onDispose(() {
    unawaited(events.cancel());
    listener.dispose();
    unawaited(socket.stop());
  });
});
