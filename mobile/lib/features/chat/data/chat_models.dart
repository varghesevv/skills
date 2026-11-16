/// Which side of a conversation a person is: the starter wrote first to a provider, the provider
/// is the one written to (ADR-0014).
enum ChatSide { starter, provider }

ChatSide _side(Object? value) => switch (value) {
  'starter' => ChatSide.starter,
  'provider' => ChatSide.provider,
  _ => throw const FormatException('side'),
};

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.seq,
    required this.conversationId,
    required this.senderSide,
    required this.body,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, Object?> json) => ChatMessage(
    id: json['id'] as String,
    seq: json['seq'] as int,
    conversationId: json['conversation_id'] as String,
    senderSide: _side(json['sender_side']),
    body: json['body'] as String,
    createdAt: DateTime.parse(json['created_at'] as String).toUtc(),
  );

  final String id;
  final int seq;
  final String conversationId;
  final ChatSide senderSide;
  final String body;
  final DateTime createdAt;
}

class Conversation {
  const Conversation({
    required this.id,
    required this.mySide,
    required this.otherId,
    required this.otherName,
    required this.otherClosed,
    required this.preview,
    required this.lastMessageAt,
    required this.unread,
    required this.muted,
    required this.blocked,
  });

  factory Conversation.fromJson(Map<String, Object?> json) {
    final other = Map<String, Object?>.from(json['other'] as Map);
    return Conversation(
      id: json['id'] as String,
      mySide: _side(json['my_side']),
      otherId: other['id'] as String,
      otherName: other['full_name'] as String?,
      otherClosed: other['closed'] as bool,
      preview: json['last_message_preview'] as String?,
      lastMessageAt: json['last_message_at'] == null
          ? null
          : DateTime.parse(json['last_message_at'] as String).toUtc(),
      unread: json['unread_count'] as int,
      muted: json['muted'] as bool,
      blocked: json['blocked'] as bool,
    );
  }

  final String id;
  final ChatSide mySide;
  final String otherId;

  /// Empty once the other person closed their account.
  final String? otherName;
  final bool otherClosed;
  final String? preview;
  final DateTime? lastMessageAt;
  final int unread;
  final bool muted;

  /// The provider's own block; a starter is never told of one.
  final bool blocked;

  Conversation copyWith({int? unread, bool? muted, bool? blocked}) =>
      Conversation(
        id: id,
        mySide: mySide,
        otherId: otherId,
        otherName: otherName,
        otherClosed: otherClosed,
        preview: preview,
        lastMessageAt: lastMessageAt,
        unread: unread ?? this.unread,
        muted: muted ?? this.muted,
        blocked: blocked ?? this.blocked,
      );
}

/// Why a conversation is reported; the codes are the API's.
const chatReportReasons = [
  'spam',
  'harassment',
  'inappropriate',
  'scam',
  'other',
];
