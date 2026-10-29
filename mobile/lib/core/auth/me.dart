import 'user_type.dart';

/// The signed-in account (`GET /me`).
class Me {
  const Me({
    required this.id,
    required this.userType,
    required this.email,
    required this.mobileNumber,
    required this.fullName,
    required this.orgName,
    required this.approvalStatus,
    required this.createdAt,
  });

  factory Me.fromJson(Map<String, Object?> json) => Me(
    id: json['id'] as String,
    userType: UserType.fromWire(json['user_type'] as String),
    email: json['email'] as String,
    mobileNumber: json['mobile_number'] as String,
    fullName: json['full_name'] as String?,
    orgName: json['org_name'] as String?,
    approvalStatus: json['approval_status'] as String?,
    createdAt: DateTime.parse(json['created_at'] as String),
  );

  final String id;
  final UserType userType;
  final String email;
  final String mobileNumber;
  final String? fullName;
  final String? orgName;
  final String? approvalStatus;
  final DateTime createdAt;

  /// What the dashboard greets: the organisation name, else the full name, else the email.
  String get displayName => orgName ?? fullName ?? email;
}
