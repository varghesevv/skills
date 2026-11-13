import 'account.dart';

/// The statuses of the church trust model, as the server names them. Which screens a person
/// sees depends on this, read from the server (`GET /me`), never from the token.
enum PersonStatus {
  revoked,
  pending,
  searcher,
  provider,
  verifier,
  admin,
  owner;

  /// A leader: VERIFIER or higher. They see the applicants and members of their scope.
  bool get isLeader => index >= PersonStatus.verifier.index;

  static PersonStatus fromWire(String value) => PersonStatus.values.firstWhere(
    (status) => status.name == value,
    orElse: () => throw const FormatException('Unknown status'),
  );
}

class NamedRef {
  const NamedRef({required this.id, required this.name});

  factory NamedRef.fromJson(Map<String, Object?> json) =>
      NamedRef(id: json['id'] as String, name: json['name'] as String);

  final String id;
  final String name;
}

/// A person of the church trust model (`GET /me` with `user_type` `person`).
class PersonMe extends Account {
  const PersonMe({
    required this.id,
    required this.fullName,
    required this.email,
    required this.mobileNumber,
    required this.status,
    required this.requestedStatus,
    required this.church,
    required this.homeGroup,
    required this.leaderName,
    required this.statusSetByName,
    required this.flaggedForRecheck,
    required this.vouchCount,
  });

  factory PersonMe.fromJson(Map<String, Object?> json) {
    final group = json['home_group'] as Map?;
    final leader = json['leader'] as Map?;
    final setBy = json['status_set_by'] as Map?;
    return PersonMe(
      id: json['id'] as String,
      fullName: json['full_name'] as String,
      email: json['email'] as String,
      mobileNumber: json['mobile_number'] as String,
      status: PersonStatus.fromWire(json['status'] as String),
      requestedStatus: json['requested_status'] as String?,
      church: NamedRef.fromJson(
        Map<String, Object?>.from(json['church'] as Map),
      ),
      homeGroup: group == null
          ? null
          : NamedRef.fromJson(Map<String, Object?>.from(group)),
      leaderName: leader?['name'] as String?,
      statusSetByName: setBy?['name'] as String?,
      flaggedForRecheck: json['flagged_for_recheck'] as bool,
      vouchCount: json['vouch_count'] as int,
    );
  }

  final String id;
  final String fullName;
  final String email;
  final String mobileNumber;
  final PersonStatus status;

  /// `searcher` or `provider`: what an applicant applied for.
  final String? requestedStatus;
  final NamedRef church;
  final NamedRef? homeGroup;
  final String? leaderName;
  final String? statusSetByName;
  final bool flaggedForRecheck;
  final int vouchCount;
}
