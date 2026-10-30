import '../../../core/api/api_client.dart';
import '../../../core/api/parse.dart';
import 'freelancer_profile.dart';

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
}
