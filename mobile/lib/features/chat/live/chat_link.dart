import 'dart:async';

import 'package:web_socket_channel/web_socket_channel.dart';

/// One open connection to the chat socket, as the client needs it. A thin layer over the
/// platform's WebSocket so that tests can stand in for the server.
abstract class ChatLink {
  /// Text frames from the server; completes when the connection ends.
  Stream<String> get frames;

  void send(String text);

  /// The close code the server gave, once the connection has ended.
  int? get closeCode;

  Future<void> close();
}

typedef ChatConnector = Future<ChatLink> Function(Uri address);

/// The real connector. Throws when the server cannot be reached.
Future<ChatLink> connectWebSocket(Uri address) async {
  final channel = WebSocketChannel.connect(address);
  await channel.ready;
  return _WebSocketLink(channel);
}

class _WebSocketLink implements ChatLink {
  _WebSocketLink(this._channel);

  final WebSocketChannel _channel;

  @override
  Stream<String> get frames =>
      _channel.stream.where((frame) => frame is String).cast<String>();

  @override
  void send(String text) => _channel.sink.add(text);

  @override
  int? get closeCode => _channel.closeCode;

  @override
  Future<void> close() => _channel.sink.close();
}
