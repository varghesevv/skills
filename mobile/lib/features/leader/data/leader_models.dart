/// A voucher as a leader sees it: a name and where they belong, never a number.
class Voucher {
  const Voucher({
    required this.name,
    required this.churchName,
    required this.live,
  });

  factory Voucher.fromJson(Map<String, Object?> json) => Voucher(
    name: json['name'] as String,
    churchName: json['church_name'] as String,
    live: json['live'] as bool,
  );

  final String name;
  final String churchName;

  /// A withdrawn vouch, or one by someone no longer admitted, does not count.
  final bool live;
}

class IdName {
  const IdName({required this.id, required this.name});

  factory IdName.fromJson(Map<String, Object?> json) =>
      IdName(id: json['id'] as String, name: json['name'] as String);

  final String id;
  final String name;
}

List<Voucher> _vouchers(Object? list) => [
  for (final item in list as List)
    Voucher.fromJson(Map<String, Object?>.from(item as Map)),
];

IdName? _idName(Object? value) =>
    value is Map ? IdName.fromJson(Map<String, Object?>.from(value)) : null;

String? _nameOf(Object? value) =>
    value is Map ? value['name'] as String? : null;

class ApplicantRow {
  const ApplicantRow({
    required this.id,
    required this.fullName,
    required this.status,
    required this.requestedStatus,
    required this.homeGroup,
    required this.appliedAt,
    required this.vouchCount,
    required this.vouchers,
    required this.canAdmitAsProvider,
  });

  factory ApplicantRow.fromJson(Map<String, Object?> json) => ApplicantRow(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    // Older answers had only applicants; a missing status means PENDING.
    status: json['status'] as String? ?? 'pending',
    requestedStatus: json['requested_status'] as String?,
    homeGroup: _idName(json['home_group'])!,
    appliedAt: DateTime.parse(json['applied_at'] as String),
    vouchCount: json['vouch_count'] as int,
    vouchers: _vouchers(json['vouchers']),
    canAdmitAsProvider: json['can_admit_as_provider'] as bool,
  );

  final String id;
  final String fullName;

  /// `pending`, or `searcher` for someone who asks to become a provider.
  final String status;
  final String? requestedStatus;
  final IdName homeGroup;
  final DateTime appliedAt;
  final int vouchCount;
  final List<Voucher> vouchers;

  /// Whether admitting as a provider will work now. It only switches the button off; the server
  /// decides.
  final bool canAdmitAsProvider;
}

class MemberRow {
  const MemberRow({
    required this.id,
    required this.fullName,
    required this.status,
    required this.homeGroupName,
    required this.statusSetByName,
    required this.flaggedForRecheck,
  });

  factory MemberRow.fromJson(Map<String, Object?> json) => MemberRow(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    status: json['status'] as String,
    homeGroupName: _idName(json['home_group'])?.name,
    statusSetByName: _nameOf(json['status_set_by']),
    flaggedForRecheck: json['flagged_for_recheck'] as bool,
  );

  final String id;
  final String fullName;
  final String status;
  final String? homeGroupName;
  final String? statusSetByName;
  final bool flaggedForRecheck;
}

/// A page of a list, with how many there are in all.
class LeaderPage<T> {
  const LeaderPage({required this.items, required this.total});

  final List<T> items;
  final int total;
}

class HistoryEntry {
  const HistoryEntry({
    required this.kind,
    required this.fromStatus,
    required this.toStatus,
    required this.changedByName,
    required this.at,
  });

  factory HistoryEntry.fromJson(Map<String, Object?> json) => HistoryEntry(
    kind: json['kind'] as String,
    fromStatus: json['from_status'] as String?,
    toStatus: json['to_status'] as String,
    changedByName: _nameOf(json['changed_by']),
    at: DateTime.parse(json['at'] as String),
  );

  final String kind;
  final String? fromStatus;
  final String toStatus;
  final String? changedByName;
  final DateTime at;
}

/// A revoked person in the leader's scope, with the group they were removed from.
class RevokedRow {
  const RevokedRow({
    required this.id,
    required this.fullName,
    required this.removedFromName,
    required this.revokedByName,
    required this.revokedAt,
  });

  factory RevokedRow.fromJson(Map<String, Object?> json) => RevokedRow(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    removedFromName: _idName(json['removed_from'])?.name,
    revokedByName: _nameOf(json['revoked_by']),
    revokedAt: json['revoked_at'] == null
        ? null
        : DateTime.parse(json['revoked_at'] as String),
  );

  final String id;
  final String fullName;
  final String? removedFromName;
  final String? revokedByName;
  final DateTime? revokedAt;
}

/// A person whose status was set by someone since revoked: they keep access until a leader
/// confirms them.
class FlaggedRow {
  const FlaggedRow({
    required this.id,
    required this.fullName,
    required this.status,
    required this.homeGroupName,
    required this.statusSetByName,
  });

  factory FlaggedRow.fromJson(Map<String, Object?> json) => FlaggedRow(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    status: json['status'] as String,
    homeGroupName: _idName(json['home_group'])?.name,
    statusSetByName: _nameOf(json['status_set_by']),
  );

  final String id;
  final String fullName;
  final String status;
  final String? homeGroupName;
  final String? statusSetByName;
}

/// The answer to a revocation, a reinstatement or a re-confirmation.
class StatusResult {
  const StatusResult({
    required this.status,
    required this.homeGroupId,
    required this.flaggedForRecheck,
  });

  factory StatusResult.fromJson(Map<String, Object?> json) => StatusResult(
    status: json['status'] as String,
    homeGroupId: json['home_group_id'] as String?,
    flaggedForRecheck: json['flagged_for_recheck'] as bool? ?? false,
  );

  final String status;
  final String? homeGroupId;
  final bool flaggedForRecheck;
}

class ChainLink {
  const ChainLink({
    required this.id,
    required this.fullName,
    required this.status,
  });

  factory ChainLink.fromJson(Map<String, Object?> json) => ChainLink(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    status: json['status'] as String,
  );

  final String id;
  final String fullName;
  final String status;
}

/// One person in the leader's scope. This answer holds the mobile number, so it is kept in the
/// screen that asked and nowhere else (every ask is recorded by the server).
class PersonDetail {
  const PersonDetail({
    required this.id,
    required this.fullName,
    required this.mobileNumber,
    required this.status,
    required this.requestedStatus,
    required this.churchId,
    required this.churchName,
    required this.homeGroupId,
    required this.homeGroupName,
    required this.statusSetByName,
    required this.flaggedForRecheck,
    required this.appliedAt,
    required this.history,
    required this.chain,
    required this.vouches,
    required this.canAdmitAsProvider,
  });

  factory PersonDetail.fromJson(Map<String, Object?> json) => PersonDetail(
    id: json['id'] as String,
    fullName: json['full_name'] as String,
    mobileNumber: json['mobile_number'] as String,
    status: json['status'] as String,
    requestedStatus: json['requested_status'] as String?,
    churchId: _idName(json['church'])!.id,
    churchName: _idName(json['church'])!.name,
    homeGroupId: _idName(json['home_group'])?.id,
    homeGroupName: _idName(json['home_group'])?.name,
    statusSetByName: _nameOf(json['status_set_by']),
    flaggedForRecheck: json['flagged_for_recheck'] as bool? ?? false,
    appliedAt: DateTime.parse(json['applied_at'] as String),
    history: [
      for (final item in json['history'] as List)
        HistoryEntry.fromJson(Map<String, Object?>.from(item as Map)),
    ],
    chain: [
      for (final item in json['chain_of_trust'] as List)
        ChainLink.fromJson(Map<String, Object?>.from(item as Map)),
    ],
    vouches: _vouchers(json['vouches']),
    // A server without the field (older than this app) gets the button switched off.
    canAdmitAsProvider: json['can_admit_as_provider'] as bool? ?? false,
  );

  final String id;
  final String fullName;
  final String mobileNumber;
  final String status;
  final String? requestedStatus;
  final String churchId;
  final String churchName;
  final String? homeGroupId;
  final String? homeGroupName;
  final String? statusSetByName;

  /// Set by someone since revoked: a leader confirms the status to clear it.
  final bool flaggedForRecheck;
  final DateTime appliedAt;
  final List<HistoryEntry> history;
  final List<ChainLink> chain;
  final List<Voucher> vouches;

  /// The server's answer: may the caller admit this person as a provider now?
  final bool canAdmitAsProvider;

  PersonDetail withStatus(String status, String? requestedStatus) =>
      _copy(status: status, requestedStatus: requestedStatus);

  /// After a revocation, a reinstatement or a re-confirmation: what the server's answer changed.
  PersonDetail withChange({
    required String status,
    required IdName? homeGroup,
    required bool flagged,
    required HistoryEntry entry,
  }) => _copy(
    status: status,
    requestedStatus: status == 'revoked' ? null : requestedStatus,
    homeGroup: homeGroup,
    setHomeGroup: true,
    flagged: flagged,
    // The caller set this status, and the change is the newest line of the history.
    statusSetByName: entry.changedByName,
    history: [...history, entry],
  );

  PersonDetail _copy({
    required String status,
    required String? requestedStatus,
    IdName? homeGroup,
    bool setHomeGroup = false,
    bool? flagged,
    String? statusSetByName,
    List<HistoryEntry>? history,
  }) => PersonDetail(
    id: id,
    fullName: fullName,
    mobileNumber: mobileNumber,
    status: status,
    requestedStatus: requestedStatus,
    churchId: churchId,
    churchName: churchName,
    homeGroupId: setHomeGroup ? homeGroup?.id : homeGroupId,
    homeGroupName: setHomeGroup ? homeGroup?.name : homeGroupName,
    statusSetByName: statusSetByName ?? this.statusSetByName,
    flaggedForRecheck: flagged ?? flaggedForRecheck,
    appliedAt: appliedAt,
    history: history ?? this.history,
    chain: chain,
    vouches: vouches,
    canAdmitAsProvider: canAdmitAsProvider,
  );
}

class AdmitResult {
  const AdmitResult({required this.status, required this.requestedStatus});

  factory AdmitResult.fromJson(Map<String, Object?> json) => AdmitResult(
    status: json['status'] as String,
    requestedStatus: json['requested_status'] as String?,
  );

  final String status;
  final String? requestedStatus;
}
