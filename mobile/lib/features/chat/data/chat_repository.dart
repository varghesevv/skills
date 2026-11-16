import '../../../core/api/api_client.dart';
import '../../../core/api/paged.dart';
import '../../../core/api/parse.dart';
import 'chat_models.dart';

/// Chat over REST (docs/specification/04-api.md). REST is the source of truth: the socket only
/// brings news sooner. Message text is passed through and never logged.
class ChatRepository {
  ChatRepository(this._api);

  final ApiClient _api;

  Future<Paged<Conversation>> conversations({int page = 1}) async =>
      parseResponse(
        await _api.get(
          '/chat/conversations',
          query: {'page': page, 'page_size': 50},
        ),
        (json) => Paged.fromJson(json, Conversation.fromJson),
      );

  /// Starts a conversation with a provider, or returns the one that exists.
  Future<Conversation> start(String providerId) async => parseResponse(
    await _api.post('/chat/conversations', body: {'provider_id': providerId}),
    Conversation.fromJson,
  );

  /// Newest first. [beforeSeq] is the cursor: the oldest `seq` already shown.
  Future<List<ChatMessage>> messages(String id, {int? beforeSeq}) async =>
      parseListResponse(
        await _api.get(
          '/chat/conversations/$id/messages',
          query: {'limit': 50, 'before_seq': ?beforeSeq},
        ),
        ChatMessage.fromJson,
      );

  /// Idempotent: sending the same [clientMessageId] again returns the stored message.
  Future<ChatMessage> send(
    String id, {
    required String clientMessageId,
    required String body,
  }) async => parseResponse(
    await _api.post(
      '/chat/conversations/$id/messages',
      body: {'client_message_id': clientMessageId, 'body': body},
    ),
    ChatMessage.fromJson,
  );

  Future<void> markRead(String id, int upToSeq) async {
    await _api.post(
      '/chat/conversations/$id/read',
      body: {'up_to_seq': upToSeq},
    );
  }

  Future<Conversation> settings(
    String id, {
    bool? muted,
    bool? blocked,
  }) async => parseResponse(
    await _api.put(
      '/chat/conversations/$id/settings',
      body: {'muted': ?muted, 'blocked': ?blocked},
    ),
    Conversation.fromJson,
  );

  Future<void> report(String id, String reason, {String? note}) async {
    await _api.post(
      '/chat/conversations/$id/report',
      body: {
        'reason': reason,
        if (note != null && note.isNotEmpty) 'note': note,
      },
    );
  }

  Future<int> unread() async => parseResponse(
    await _api.get('/chat/unread'),
    (json) => json['total'] as int,
  );

  /// A phone's push address (S8.9); the id is kept to forget it at sign-out.
  Future<String> registerDevice(String token) async => parseResponse(
    await _api.post(
      '/chat/devices',
      body: {'token': token, 'platform': 'android'},
    ),
    (json) => json['id'] as String,
  );

  Future<void> forgetDevice(String id) async {
    await _api.delete('/chat/devices/$id');
  }
}
