import '../../../core/api/api_client.dart';
import '../../../core/api/parse.dart';
import 'leader_models.dart';

/// The verifier screens' calls (docs/specification/04-api.md). Lists carry no phone numbers; only
/// [personDetail] does, and the server records each ask.
class LeaderRepository {
  LeaderRepository(this._api);

  final ApiClient _api;

  static const pageSize = 50;

  Future<LeaderPage<ApplicantRow>> applicants({int offset = 0}) async =>
      parseResponse(
        await _api.get(
          '/verifier/applicants',
          query: {'limit': pageSize, 'offset': offset},
        ),
        (json) => LeaderPage(
          items: [
            for (final item in json['items'] as List)
              ApplicantRow.fromJson(Map<String, Object?>.from(item as Map)),
          ],
          total: json['total'] as int,
        ),
      );

  Future<LeaderPage<MemberRow>> members({
    int offset = 0,
    String? status,
    String? homeGroupId,
    String? churchId,
  }) async => parseResponse(
    await _api.get(
      '/verifier/members',
      query: {
        'limit': pageSize,
        'offset': offset,
        'status': ?status,
        'home_group_id': ?homeGroupId,
        'church_id': ?churchId,
      },
    ),
    (json) => LeaderPage(
      items: [
        for (final item in json['items'] as List)
          MemberRow.fromJson(Map<String, Object?>.from(item as Map)),
      ],
      total: json['total'] as int,
    ),
  );

  /// Throws `ApiException` (`not_found` for anyone out of scope, closed or unknown).
  Future<PersonDetail> personDetail(String id) async => parseResponse(
    await _api.get('/verifier/people/$id'),
    PersonDetail.fromJson,
  );

  /// Throws `ApiException` (`not_enough_vouches`, `not_pending`, `state_changed`, `not_found`).
  Future<AdmitResult> admit(String id, String to) async => parseResponse(
    await _api.post('/verifier/people/$id/admit', body: {'to': to}),
    AdmitResult.fromJson,
  );

  Future<void> decline(String id) async {
    await _api.post('/verifier/people/$id/decline');
  }

  Future<LeaderPage<RevokedRow>> revoked({int offset = 0}) async =>
      parseResponse(
        await _api.get(
          '/verifier/revoked',
          query: {'limit': pageSize, 'offset': offset},
        ),
        (json) => LeaderPage(
          items: [
            for (final item in json['items'] as List)
              RevokedRow.fromJson(Map<String, Object?>.from(item as Map)),
          ],
          total: json['total'] as int,
        ),
      );

  Future<LeaderPage<FlaggedRow>> flagged({int offset = 0}) async =>
      parseResponse(
        await _api.get(
          '/verifier/flagged',
          query: {'limit': pageSize, 'offset': offset},
        ),
        (json) => LeaderPage(
          items: [
            for (final item in json['items'] as List)
              FlaggedRow.fromJson(Map<String, Object?>.from(item as Map)),
          ],
          total: json['total'] as int,
        ),
      );

  /// Revoke someone below you. Throws `ApiException` (`status_not_allowed`, `already_revoked`,
  /// `successor_required` for a leader, `not_found`).
  Future<StatusResult> revoke(String id) async => parseResponse(
    await _api.put('/verifier/people/$id/status', body: {'to': 'revoked'}),
    StatusResult.fromJson,
  );

  /// Bring a revoked person back into a home group of their church, as a searcher or a provider.
  Future<StatusResult> reinstate(
    String id,
    String to,
    String homeGroupId,
  ) async => parseResponse(
    await _api.put(
      '/verifier/people/$id/status',
      body: {'to': to, 'home_group_id': homeGroupId},
    ),
    StatusResult.fromJson,
  );

  /// Clear a re-check flag: the caller becomes the new link in the person's chain of trust.
  Future<StatusResult> reconfirm(String id) async => parseResponse(
    await _api.post('/verifier/people/$id/reconfirm'),
    StatusResult.fromJson,
  );
}
