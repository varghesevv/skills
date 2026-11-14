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
}
