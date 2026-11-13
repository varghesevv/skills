/// Whether the person has a vouch link that still works. The token is never returned again.
class VouchLinkState {
  const VouchLinkState({required this.active, required this.expiresAt});

  factory VouchLinkState.fromJson(Map<String, Object?> json) => VouchLinkState(
    active: json['active'] as bool,
    expiresAt: _date(json['expires_at']),
  );

  final bool active;
  final DateTime? expiresAt;
}

/// A new link. The token is shown once; only a hash is kept on the server.
class VouchLinkCreated {
  const VouchLinkCreated({required this.token, required this.expiresAt});

  factory VouchLinkCreated.fromJson(Map<String, Object?> json) =>
      VouchLinkCreated(
        token: json['token'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );

  final String token;
  final DateTime expiresAt;
}

/// Who a vouch link is for: a name and where they belong, never a number.
class VouchLinkInfo {
  const VouchLinkInfo({
    required this.applicantName,
    required this.churchName,
    required this.homeGroupName,
    required this.requestedStatus,
    required this.alreadyVouched,
  });

  factory VouchLinkInfo.fromJson(Map<String, Object?> json) => VouchLinkInfo(
    applicantName: json['applicant_name'] as String,
    churchName: json['church_name'] as String,
    homeGroupName: json['home_group_name'] as String,
    requestedStatus: json['requested_status'] as String,
    alreadyVouched: json['already_vouched'] as bool,
  );

  final String applicantName;
  final String churchName;
  final String homeGroupName;
  final String requestedStatus; // searcher or provider
  final bool alreadyVouched;
}

class VouchReceived {
  const VouchReceived({
    required this.id,
    required this.voucherName,
    required this.churchName,
    required this.live,
    required this.createdAt,
  });

  factory VouchReceived.fromJson(Map<String, Object?> json) => VouchReceived(
    id: json['id'] as String,
    voucherName: json['voucher_name'] as String,
    churchName: json['church_name'] as String,
    live: json['live'] as bool,
    createdAt: DateTime.parse(json['created_at'] as String),
  );

  final String id;
  final String voucherName;
  final String churchName;

  /// A withdrawn vouch, or one by someone no longer admitted, does not count.
  final bool live;
  final DateTime createdAt;
}

class VouchGiven {
  const VouchGiven({
    required this.id,
    required this.applicantName,
    required this.withdrawn,
    required this.canWithdraw,
    required this.createdAt,
  });

  factory VouchGiven.fromJson(Map<String, Object?> json) => VouchGiven(
    id: json['id'] as String,
    applicantName: json['applicant_name'] as String,
    withdrawn: json['withdrawn'] as bool,
    canWithdraw: json['can_withdraw'] as bool,
    createdAt: DateTime.parse(json['created_at'] as String),
  );

  final String id;
  final String applicantName; // empty once their account is closed
  final bool withdrawn;
  final bool canWithdraw; // until the applicant is admitted
  final DateTime createdAt;
}

class NotificationItem {
  const NotificationItem({
    required this.id,
    required this.kind,
    required this.subjectName,
    required this.createdAt,
    required this.read,
  });

  factory NotificationItem.fromJson(Map<String, Object?> json) {
    final subject = json['subject'];
    return NotificationItem(
      id: json['id'] as String,
      kind: json['kind'] as String,
      subjectName: subject is Map ? (subject['name'] as String? ?? '') : '',
      createdAt: DateTime.parse(json['created_at'] as String),
      read: json['read'] as bool,
    );
  }

  final String id;
  final String kind;
  final String subjectName; // empty for a closed account or no subject
  final DateTime createdAt;
  final bool read;
}

class NotificationList {
  const NotificationList({required this.items, required this.unreadCount});

  factory NotificationList.fromJson(Map<String, Object?> json) =>
      NotificationList(
        items: [
          for (final item in json['items'] as List)
            NotificationItem.fromJson(Map<String, Object?>.from(item as Map)),
        ],
        unreadCount: json['unread_count'] as int,
      );

  final List<NotificationItem> items;
  final int unreadCount;
}

DateTime? _date(Object? value) =>
    value == null ? null : DateTime.parse(value as String);

/// The address a person sends to people who know them. The web page lives on the same host as
/// the API, so the address is the API address without its `/api/v1` path.
String vouchLinkFor(String token, {required String apiBase}) {
  final uri = Uri.tryParse(apiBase);
  final origin = uri == null || !uri.hasAuthority ? '' : uri.origin;
  return '$origin/vouch/$token';
}
