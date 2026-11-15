import '../../core/auth/person_me.dart';
import '../freelancer/data/label.dart';
import '../freelancer/data/unavailability.dart';

/// The rating the caller gave a provider (`my_rating`, and the answer of the rating calls).
class GivenRating {
  const GivenRating({
    required this.id,
    required this.providerId,
    required this.providerName,
    required this.rating,
    required this.comment,
    required this.ratedOn,
  });

  factory GivenRating.fromJson(Map<String, Object?> json) => GivenRating(
    id: json['id'] as String,
    providerId: json['provider_id'] as String,
    providerName: json['provider_name'] as String?,
    rating: json['rating'] as int,
    comment: json['comment'] as String?,
    ratedOn: DateTime.parse(json['rated_on'] as String).toUtc(),
  );

  final String id;
  final String providerId;
  final String? providerName;
  final int rating; // 1 to 10
  final String? comment;
  final DateTime ratedOn;
}

/// A provider as a SEARCHER or above sees them (`GET /freelancers/{id}`): never an email or a
/// mobile number; the number comes from the Reveal endpoint only.
class ProviderPublic {
  const ProviderPublic({
    required this.id,
    required this.fullName,
    required this.whatsapp,
    required this.nationality,
    required this.primaryLanguage,
    required this.ratePerHour,
    required this.rateCurrency,
    required this.isRateNegotiable,
    required this.labels,
    required this.averageRating,
    required this.ratingCount,
    required this.church,
    required this.homeGroup,
    required this.unavailable,
    required this.myRating,
  });

  factory ProviderPublic.fromJson(Map<String, Object?> json) => ProviderPublic(
    id: json['id'] as String,
    fullName: json['full_name'] as String?,
    whatsapp: (json['whatsapp_availability'] as bool?) ?? false,
    nationality: json['nationality'] as String?,
    primaryLanguage: json['primary_language'] as String?,
    ratePerHour: (json['rate_per_hour'] as num?)?.toDouble(),
    rateCurrency: json['rate_currency'] as String?,
    isRateNegotiable: (json['is_rate_negotiable'] as bool?) ?? false,
    labels: [
      for (final l in json['labels'] as List)
        ProfileLabel.fromJson(Map<String, Object?>.from(l as Map)),
    ],
    averageRating: (json['average_rating'] as num?)?.toDouble(),
    ratingCount: json['rating_count'] as int,
    church: NamedRef.fromJson(Map<String, Object?>.from(json['church'] as Map)),
    homeGroup: NamedRef.fromJson(
      Map<String, Object?>.from(json['home_group'] as Map),
    ),
    unavailable: [
      for (final u in json['unavailable'] as List)
        Unavailability.fromJson(Map<String, Object?>.from(u as Map)),
    ],
    myRating: json['my_rating'] == null
        ? null
        : GivenRating.fromJson(
            Map<String, Object?>.from(json['my_rating'] as Map),
          ),
  );

  final String id;
  final String? fullName;
  final bool whatsapp;
  final String? nationality;
  final String? primaryLanguage;
  final double? ratePerHour;
  final String? rateCurrency;
  final bool isRateNegotiable;
  final List<ProfileLabel> labels;
  final double? averageRating;
  final int ratingCount;
  final NamedRef church;
  final NamedRef homeGroup;
  final List<Unavailability> unavailable;
  final GivenRating? myRating;
}
