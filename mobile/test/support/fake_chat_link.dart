import 'dart:async';

import 'package:skills_app/features/chat/live/chat_link.dart';

/// A stand-in for the chat server: it keeps what the client sent and says what the test tells it
/// to say. Nothing real is contacted.
class FakeLink implements ChatLink {
  final _frames = StreamController<String>();
  final sent = <String>[];
  int? _closeCode;
  bool closedByClient = false;

  @override
  Stream<String> get frames => _frames.stream;

  @override
  void send(String text) => sent.add(text);

  @override
  int? get closeCode => _closeCode;

  @override
  Future<void> close() async {
    closedByClient = true;
    if (!_frames.isClosed) await _frames.close();
  }

  /// The server says something.
  void say(String frame) => _frames.add(frame);

  /// The server ends the connection with a close code.
  Future<void> serverClose(int code) async {
    _closeCode = code;
    await _frames.close();
  }

  /// The connection drops without a close code.
  Future<void> drop() => _frames.close();
}

/// Hands out a new [FakeLink] for every connection and remembers them. [failures] first
/// attempts fail as if the server could not be reached.
class FakeServer {
  FakeServer({this.failures = 0});

  int failures;
  final links = <FakeLink>[];
  final addresses = <Uri>[];

  Future<ChatLink> connect(Uri address) async {
    addresses.add(address);
    if (failures > 0) {
      failures--;
      throw StateError('unreachable');
    }
    final link = FakeLink();
    links.add(link);
    return link;
  }

  FakeLink get last => links.last;
}

/// A connector that never answers: for screens where the socket is not under test, so that no
/// timer or network is involved.
Future<ChatLink> neverConnects(Uri address) => Completer<ChatLink>().future;
