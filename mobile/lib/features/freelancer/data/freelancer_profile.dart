/// The signed-in freelancer's own profile (`GET /freelancers/me`).
class FreelancerProfile {
  const FreelancerProfile({
    required this.id,
    required this.fullName,
    required this.email,
    required this.mobileNumber,
    required this.whatsappAvailability,
    required this.nationality,
    required this.primaryLanguage,
    required this.ratePerHour,
    required this.rateCurrency,
    required this.isRateNegotiable,
  });

  factory FreelancerProfile.fromJson(Map<String, Object?> json) =>
      FreelancerProfile(
        id: json['id'] as String,
        fullName: json['full_name'] as String?,
        email: json['email'] as String,
        mobileNumber: json['mobile_number'] as String,
        whatsappAvailability: json['whatsapp_availability'] as bool,
        nationality: json['nationality'] as String?,
        primaryLanguage: json['primary_language'] as String?,
        ratePerHour: (json['rate_per_hour'] as num?)?.toDouble(),
        rateCurrency: json['rate_currency'] as String?,
        isRateNegotiable: json['is_rate_negotiable'] as bool,
      );

  final String id;
  final String? fullName;
  final String email;
  final String mobileNumber;
  final bool whatsappAvailability;
  final String? nationality;
  final String? primaryLanguage;
  final double? ratePerHour;
  final String? rateCurrency;
  final bool isRateNegotiable;
}

/// What the profile form sends (`PUT /freelancers/me`). Empty optional text and an empty rate
/// are sent as `null`, so the API stores nothing.
class FreelancerProfileUpdate {
  const FreelancerProfileUpdate({
    required this.fullName,
    required this.mobileNumber,
    required this.whatsappAvailability,
    required this.nationality,
    required this.primaryLanguage,
    required this.ratePerHour,
    required this.rateCurrency,
    required this.isRateNegotiable,
  });

  final String fullName;
  final String mobileNumber; // already normalised
  final bool whatsappAvailability;
  final String? nationality;
  final String? primaryLanguage;
  final double? ratePerHour;
  final String? rateCurrency;
  final bool isRateNegotiable;

  Map<String, Object?> toJson() => {
    'full_name': fullName,
    'mobile_number': mobileNumber,
    'whatsapp_availability': whatsappAvailability,
    'nationality': nationality,
    'primary_language': primaryLanguage,
    'rate_per_hour': ratePerHour,
    'rate_currency': rateCurrency,
    'is_rate_negotiable': isRateNegotiable,
  };
}
