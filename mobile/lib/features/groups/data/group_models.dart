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
