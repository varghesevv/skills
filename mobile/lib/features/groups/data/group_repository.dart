import '../../../core/api/api_client.dart';
import '../../../core/api/parse.dart';
import '../../leader/data/leader_models.dart';
import 'group_models.dart';

/// The calls to start a home group (docs/specification/04-api.md).
class GroupRepository {
  GroupRepository(this._api);

  final ApiClient _api;

  static const pageSize = 50;

  /// An ADMIN sees the open requests of their church (the OWNER those of every church); anyone
  /// else their own.
  Future<LeaderPage<GroupRequestRow>> requests({int offset = 0}) async =>
      parseResponse(
        await _api.get(
          '/group-requests',
          query: {'limit': pageSize, 'offset': offset},
        ),
        (json) => LeaderPage(
          items: [
            for (final item in json['items'] as List)
              GroupRequestRow.fromJson(Map<String, Object?>.from(item as Map)),
          ],
          total: json['total'] as int,
        ),
      );

  /// An ADMIN or the OWNER start the group at once. Throws `ApiException` (`group_name_taken`,
  /// `request_open`, `successor_required`, `not_admitted`).
  Future<GroupAsked> ask(String name, {String? successorId}) async =>
      parseResponse(
        await _api.post(
          '/group-requests',
          body: {'group_name': name, 'successor_id': ?successorId},
        ),
        GroupAsked.fromJson,
      );

  /// Throws `ApiException` (`not_open`, `successor_required`, `successor_not_member`,
  /// `requester_unavailable`, `group_name_taken`).
  Future<String> approve(String id, {String? successorId}) async =>
      parseResponse(
        await _api.post(
          '/group-requests/$id/approve',
          body: {'successor_id': ?successorId},
        ),
        (json) => (json['group'] as Map)['name'] as String,
      );

  Future<void> decline(String id) async {
    await _api.post('/group-requests/$id/decline');
  }

  /// The moves that concern you, as the member or as the leader of either group, newest first.
  Future<LeaderPage<MoveRow>> moves({int offset = 0}) async => parseResponse(
    await _api.get(
      '/move-requests',
      query: {'limit': pageSize, 'offset': offset},
    ),
    (json) => LeaderPage(
      items: [
        for (final item in json['items'] as List)
          MoveRow.fromJson(Map<String, Object?>.from(item as Map)),
      ],
      total: json['total'] as int,
    ),
  );

  /// Asking is the member's own agreement; the leaders of both groups must agree too. Throws
  /// `ApiException` (`request_open`, `invalid_choice`, `leads_a_group`, `not_admitted`).
  Future<MoveRow> askToMove(String homeGroupId) async => parseResponse(
    await _api.post('/move-requests', body: {'home_group_id': homeGroupId}),
    MoveRow.fromJson,
  );

  /// Throws `ApiException` (`not_open`, `already_agreed`, `request_stale`, `not_found`).
  Future<MoveRow> agree(String id) async => parseResponse(
    await _api.post('/move-requests/$id/agree'),
    MoveRow.fromJson,
  );

  Future<MoveRow> cancel(String id) async => parseResponse(
    await _api.post('/move-requests/$id/cancel'),
    MoveRow.fromJson,
  );

  /// An ADMIN or the OWNER replace the leader of a group, or hand on their own, with a member of
  /// it. [former] is `provider` or `searcher` for a VERIFIER, `keep` for an ADMIN or the OWNER.
  /// Throws `ApiException` (`successor_not_member`, `invalid_choice`, `status_not_allowed`,
  /// `state_changed`, `not_found`). Answers the group's name and the new leader's name.
  Future<(String group, String leader)> replaceLeader(
    String groupId,
    String successorId,
    String former,
  ) async => parseResponse(
    await _api.put(
      '/home-groups/$groupId/leader',
      body: {'successor_id': successorId, 'former_leader_status': former},
    ),
    (json) => (
      (json['group'] as Map)['name'] as String,
      (json['leader'] as Map)['name'] as String,
    ),
  );

  /// The links to the leader's group that still work, without tokens. Throws `ApiException`
  /// (`no_home_group` for an ADMIN or the OWNER who has handed their group on).
  Future<List<GroupInvitationRow>> invitations() async => parseResponse(
    await _api.get('/verifier/group-invitations'),
    (json) => [
      for (final item in json['items'] as List)
        GroupInvitationRow.fromJson(Map<String, Object?>.from(item as Map)),
    ],
  );

  /// The token is in the answer once; only a hash is kept.
  Future<GroupInvitationCreated> createInvitation() async => parseResponse(
    await _api.post('/verifier/group-invitations'),
    GroupInvitationCreated.fromJson,
  );

  Future<void> revokeInvitation(String id) async {
    await _api.delete('/verifier/group-invitations/$id');
  }
}
