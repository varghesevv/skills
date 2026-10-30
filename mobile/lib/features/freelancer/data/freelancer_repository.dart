import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/api/parse.dart';
import 'freelancer_profile.dart';
import 'label.dart';

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
}
