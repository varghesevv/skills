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
    required this.churchName,
    required this.homeGroupName,
    required this.statusSetByName,
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
    churchName: _idName(json['church'])!.name,
    homeGroupName: _idName(json['home_group'])?.name,
    statusSetByName: _nameOf(json['status_set_by']),
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
    canAdmitAsProvider: json['can_admit_as_provider'] as bool,
  );

  final String id;
  final String fullName;
  final String mobileNumber;
  final String status;
  final String? requestedStatus;
  final String churchName;
  final String? homeGroupName;
  final String? statusSetByName;
  final DateTime appliedAt;
  final List<HistoryEntry> history;
  final List<ChainLink> chain;
  final List<Voucher> vouches;

  /// The server's answer: may the caller admit this person as a provider now?
  final bool canAdmitAsProvider;

  PersonDetail withStatus(String status, String? requestedStatus) =>
      PersonDetail(
        id: id,
        fullName: fullName,
        mobileNumber: mobileNumber,
        status: status,
        requestedStatus: requestedStatus,
        churchName: churchName,
        homeGroupName: homeGroupName,
        statusSetByName: statusSetByName,
        appliedAt: appliedAt,
        history: history,
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
