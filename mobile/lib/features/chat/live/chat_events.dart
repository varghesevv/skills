import '../data/chat_models.dart';

/// What the socket tells the app.
sealed class ChatEvent {
  const ChatEvent();
}

/// The server accepted the sign-in; [again] is true when this is a reconnect, so anything
/// missed while away has to be read again over REST.
class ChatConnected extends ChatEvent {
  const ChatConnected({required this.again});

  final bool again;
}

class ChatDisconnected extends ChatEvent {
  const ChatDisconnected();
}

class ChatMessageEvent extends ChatEvent {
  const ChatMessageEvent(this.message);

  final ChatMessage message;
}

/// The other person read (or their app received) messages up to [upToSeq].
class ChatMarkEvent extends ChatEvent {
  const ChatMarkEvent({
    required this.read,
    required this.conversationId,
    required this.side,
    required this.upToSeq,
  });

  final bool read;
  final String conversationId;
  final ChatSide side;
  final int upToSeq;
}

/// A request over the socket was refused.
class ChatErrorEvent extends ChatEvent {
  const ChatErrorEvent(this.code);

  final String code;
}
