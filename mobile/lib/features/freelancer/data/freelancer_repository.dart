import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/api/paged.dart';
import '../../../core/api/parse.dart';
import 'freelancer_profile.dart';
import 'label.dart';
import 'received_rating.dart';
import 'unavailability.dart';

/// Ratings are loaded ten at a time, as on the web.
const ratingsPageSize = 10;

class FreelancerRepository {
  FreelancerRepository(this._api);

  final ApiClient _api;

  Future<FreelancerProfile> profile() async => parseResponse(
    await _api.get('/freelancers/me'),
    FreelancerProfile.fromJson,
  );

  Future<FreelancerProfile> updateProfile(
    FreelancerProfileUpdate update,
  ) async => parseResponse(
    await _api.put('/freelancers/me', body: update.toJson()),
    FreelancerProfile.fromJson,
  );

  /// Every active label (`GET /labels`): the choices on the labels screen.
  Future<List<Label>> labelCatalog() async {
    final data = await _api.get('/labels');
    if (data is! List) throw const ApiException.badResponse();
    return [for (final item in data) parseResponse(item, Label.fromJson)];
  }

  /// Replaces the whole label set (`PUT /freelancers/me/labels`).
  Future<List<ProfileLabel>> replaceLabels(
    List<LabelSelection> selection,
  ) async {
    final data = await _api.put(
      '/freelancers/me/labels',
      body: {
        'labels': [for (final s in selection) s.toJson()],
      },
    );
    if (data is! List) throw const ApiException.badResponse();
    return [
      for (final item in data) parseResponse(item, ProfileLabel.fromJson),
    ];
  }

  Future<List<Unavailability>> unavailability() async {
    final data = await _api.get('/freelancers/me/unavailability');
    if (data is! List) throw const ApiException.badResponse();
    return [
      for (final item in data) parseResponse(item, Unavailability.fromJson),
    ];
  }

  Future<Unavailability> addUnavailability(DateTime from, DateTime to) async =>
      parseResponse(
        await _api.post(
          '/freelancers/me/unavailability',
          body: periodBody(from, to),
        ),
        Unavailability.fromJson,
      );

  Future<Unavailability> updateUnavailability(
    String id,
    DateTime from,
    DateTime to,
  ) async => parseResponse(
    await _api.put(
      '/freelancers/me/unavailability/$id',
      body: periodBody(from, to),
    ),
    Unavailability.fromJson,
  );

  Future<void> deleteUnavailability(String id) async {
    await _api.delete('/freelancers/me/unavailability/$id');
  }

  /// One page of the ratings a freelancer received, newest first.
  Future<Paged<ReceivedRating>> ratings(
    String freelancerId, {
    required int page,
    int pageSize = ratingsPageSize,
  }) async => parseResponse(
    await _api.get(
      '/freelancers/$freelancerId/ratings',
      query: {'page': page, 'page_size': pageSize},
    ),
    (json) => Paged.fromJson(json, ReceivedRating.fromJson),
  );
}
