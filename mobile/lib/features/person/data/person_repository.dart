import '../../../core/api/api_client.dart';
import '../../../core/api/parse.dart';
import '../../../core/auth/person_me.dart';
import 'vouching_models.dart';

class ChurchSummary {
  const ChurchSummary({required this.id, required this.name});

  factory ChurchSummary.fromJson(Map<String, Object?> json) =>
      ChurchSummary(id: json['id'] as String, name: json['name'] as String);

  final String id;
  final String name;
}

class HomeGroupSummary {
  const HomeGroupSummary({
    required this.id,
    required this.name,
    required this.leaderName,
  });

  factory HomeGroupSummary.fromJson(Map<String, Object?> json) =>
      HomeGroupSummary(
        id: json['id'] as String,
        name: json['name'] as String,
        leaderName: json['leader_name'] as String,
      );

  final String id;
  final String name;
  final String leaderName;
}

/// What an invitation link leads to, for the sign-up screen.
class InvitationInfo {
  const InvitationInfo({
    required this.churchName,
    required this.homeGroupName,
    required this.leaderName,
  });

  factory InvitationInfo.fromJson(Map<String, Object?> json) => InvitationInfo(
    churchName: json['church_name'] as String,
    homeGroupName: json['home_group_name'] as String,
    leaderName: json['leader_name'] as String,
  );

  final String churchName;
  final String homeGroupName;
  final String leaderName;
}

/// Sign-up, the lists it needs, the change of choice and leaving, for people of the church trust
/// model (docs/specification/04-api.md). Passwords and link tokens are passed through, never
/// stored or logged; a link token travels in a request body, never in an address.
class PersonRepository {
  PersonRepository(this._api);

  final ApiClient _api;

  Future<List<ChurchSummary>> churches() async => parseResponse(
    await _api.get('/churches', auth: false),
    (json) => [
      for (final item in json['items'] as List)
        ChurchSummary.fromJson(Map<String, Object?>.from(item as Map)),
    ],
  );

  Future<List<HomeGroupSummary>> homeGroups(String churchId) async =>
      parseResponse(
        await _api.get('/churches/$churchId/home-groups', auth: false),
        (json) => [
          for (final item in json['items'] as List)
            HomeGroupSummary.fromJson(Map<String, Object?>.from(item as Map)),
        ],
      );

  /// Throws `ApiException` (`not_found`, `rate_limited`): every failure of a link looks alike.
  Future<InvitationInfo> lookupInvitation(String token) async => parseResponse(
    await _api.post(
      '/group-invitations/lookup',
      body: {'token': token},
      auth: false,
    ),
    InvitationInfo.fromJson,
  );

  /// Throws `ApiException`: `account_exists`, `invalid_choice`, `rate_limited`, `validation_error`.
  Future<void> signUp({
    required String fullName,
    required String email,
    required String mobileNumber,
    required String password,
    required String requestedStatus,
    String? homeGroupId,
    String? invitationToken,
  }) async {
    await _api.post(
      '/auth/signup',
      body: {
        'full_name': fullName,
        'email': email,
        'mobile_number': mobileNumber,
        'password': password,
        'requested_status': requestedStatus,
        if (invitationToken != null)
          'invitation_token': invitationToken
        else
          'home_group_id': homeGroupId,
      },
      auth: false,
    );
  }

  /// While pending: another home group (even in another church) or another status to apply for.
  Future<PersonMe> updateApplication({
    String? homeGroupId,
    String? requestedStatus,
  }) async => parseResponse(
    await _api.put(
      '/me/application',
      body: {
        'home_group_id': ?homeGroupId,
        'requested_status': ?requestedStatus,
      },
    ),
    PersonMe.fromJson,
  );

  /// Closes the account after the password is asked again. Throws `ApiException`
  /// (`invalid_password`, `rate_limited`, ...).
  Future<void> closeAccount(String password) async {
    await _api.delete('/me', body: {'password': password});
  }

  /// A searcher asks to become a provider. They stay a searcher; the answer is the person as
  /// `GET /me` shows them. Throws `ApiException` (`not_searcher` for anyone else).
  Future<PersonMe> applyProvider() async =>
      parseResponse(await _api.post('/me/apply-provider'), PersonMe.fromJson);

  Future<VouchLinkState> vouchLinkState() async =>
      parseResponse(await _api.get('/me/vouch-link'), VouchLinkState.fromJson);

  /// Makes a new link and ends the one before it. The token is shown once.
  Future<VouchLinkCreated> makeVouchLink() async => parseResponse(
    await _api.post('/me/vouch-link'),
    VouchLinkCreated.fromJson,
  );

  Future<List<VouchReceived>> vouchesReceived() async => parseResponse(
    await _api.get('/me/vouches'),
    (json) => [
      for (final item in json['items'] as List)
        VouchReceived.fromJson(Map<String, Object?>.from(item as Map)),
    ],
  );

  Future<List<VouchGiven>> vouchesGiven() async => parseResponse(
    await _api.get('/me/vouches-given'),
    (json) => [
      for (final item in json['items'] as List)
        VouchGiven.fromJson(Map<String, Object?>.from(item as Map)),
    ],
  );

  /// The token travels in the body, never in the address. Throws `ApiException` (`not_found`,
  /// `cannot_vouch_self`, `rate_limited`): every bad link looks alike.
  Future<VouchLinkInfo> lookupVouchLink(String token) async => parseResponse(
    await _api.post('/vouch-links/lookup', body: {'token': token}),
    VouchLinkInfo.fromJson,
  );

  /// Throws `ApiException` (`already_vouched`, `cannot_vouch_self`, `not_found`, `rate_limited`).
  Future<void> vouch(String token) async {
    await _api.post('/vouch-links/vouch', body: {'token': token});
  }

  Future<void> withdrawVouch(String id) async {
    await _api.delete('/vouches/$id');
  }

  Future<NotificationList> notifications() async => parseResponse(
    await _api.get('/me/notifications', query: {'limit': 50}),
    NotificationList.fromJson,
  );

  Future<void> markNotificationRead(String id) async {
    await _api.post('/me/notifications/$id/read');
  }

  Future<void> markAllNotificationsRead() async {
    await _api.post('/me/notifications/read-all');
  }
}
