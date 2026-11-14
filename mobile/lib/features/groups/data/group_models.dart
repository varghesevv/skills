import '../../../core/auth/person_me.dart';

/// A request to start a home group, as the app shows it.
class GroupRequestRow {
  const GroupRequestRow({
    required this.id,
    required this.groupName,
    required this.churchName,
    required this.requesterId,
    required this.requesterName,
    required this.state,
    required this.createdAt,
    required this.requesterLeadsAGroup,
    required this.requesterGroup,
  });

  factory GroupRequestRow.fromJson(Map<String, Object?> json) {
    final requester = Map<String, Object?>.from(json['requester'] as Map);
    final group = json['requester_group'];
    return GroupRequestRow(
      id: json['id'] as String,
      groupName: json['group_name'] as String,
      churchName: NamedRef.fromJson(
        Map<String, Object?>.from(json['church'] as Map),
      ).name,
      requesterId: requester['id'] as String,
      requesterName: requester['name'] as String,
      state: json['state'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      requesterLeadsAGroup: json['requester_leads_a_group'] as bool,
      // A server older than the field gives no group: the choice of successor is then empty.
      requesterGroup: group is Map
          ? NamedRef.fromJson(Map<String, Object?>.from(group))
          : null,
    );
  }

  final String id;
  final String groupName;
  final String churchName;
  final String requesterId;
  final String requesterName;

  /// `open`, `approved` or `declined`.
  final String state;
  final DateTime createdAt;

  /// Approving needs someone to lead the group the requester leads now.
  final bool requesterLeadsAGroup;

  /// The open group the requester belongs to now: whose members may lead it instead.
  final NamedRef? requesterGroup;
}

/// The answer to asking for a group: the request, and the group when it was started at once.
class GroupAsked {
  const GroupAsked({required this.request, required this.groupName});

  factory GroupAsked.fromJson(Map<String, Object?> json) => GroupAsked(
    request: GroupRequestRow.fromJson(
      Map<String, Object?>.from(json['request'] as Map),
    ),
    groupName: json['group'] is Map
        ? (json['group'] as Map)['name'] as String?
        : null,
  );

  final GroupRequestRow request;
  final String? groupName;
}

/// A move of one member to another home group of their church, by agreement.
class MoveRow {
  const MoveRow({
    required this.id,
    required this.personId,
    required this.personName,
    required this.fromGroup,
    required this.toGroup,
    required this.agreedPerson,
    required this.agreedFromLeader,
    required this.agreedToLeader,
    required this.state,
    required this.createdAt,
  });

  factory MoveRow.fromJson(Map<String, Object?> json) {
    final person = Map<String, Object?>.from(json['person'] as Map);
    final agreed = Map<String, Object?>.from(json['agreed'] as Map);
    return MoveRow(
      id: json['id'] as String,
      personId: person['id'] as String,
      personName: person['name'] as String,
      fromGroup: NamedRef.fromJson(
        Map<String, Object?>.from(json['from_group'] as Map),
      ),
      toGroup: NamedRef.fromJson(
        Map<String, Object?>.from(json['to_group'] as Map),
      ),
      agreedPerson: agreed['person'] as bool,
      agreedFromLeader: agreed['from_leader'] as bool,
      agreedToLeader: agreed['to_leader'] as bool,
      state: json['state'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  final String id;
  final String personId;
  final String personName;
  final NamedRef fromGroup;
  final NamedRef toGroup;
  final bool agreedPerson;
  final bool agreedFromLeader;
  final bool agreedToLeader;

  /// `open`, `completed` or `cancelled`.
  final String state;
  final DateTime createdAt;
}

/// An invitation link to the group a leader leads, as the list shows it: it has no token, which
/// was shown once when the link was made.
class GroupInvitationRow {
  const GroupInvitationRow({
    required this.id,
    required this.createdAt,
    required this.expiresAt,
  });

  factory GroupInvitationRow.fromJson(Map<String, Object?> json) =>
      GroupInvitationRow(
        id: json['id'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );

  final String id;
  final DateTime createdAt;
  final DateTime expiresAt;
}

/// A link just made: the token is here and nowhere else, and only until the screen is left.
class GroupInvitationCreated {
  const GroupInvitationCreated({
    required this.id,
    required this.token,
    required this.expiresAt,
  });

  factory GroupInvitationCreated.fromJson(Map<String, Object?> json) =>
      GroupInvitationCreated(
        id: json['id'] as String,
        token: json['token'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );

  final String id;
  final String token;
  final DateTime expiresAt;
}

/// The address a leader sends to people who may join their group. The page lives on the same
/// host as the API, so the address is the API address without its `/api/v1` path.
String joinLinkFor(String token, {required String apiBase}) {
  final uri = Uri.tryParse(apiBase);
  final origin = uri == null || !uri.hasAuthority ? '' : uri.origin;
  return '$origin/join/$token';
}
