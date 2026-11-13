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
  }) async => parseResponse(
    await _api.get(
      '/verifier/members',
      query: {'limit': pageSize, 'offset': offset, 'status': ?status},
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
}
