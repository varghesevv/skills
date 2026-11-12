/// A rating the freelancer received (`GET /freelancers/{id}/ratings`). The work host who gave it
/// is never shown, here or on the web.
class ReceivedRating {
  const ReceivedRating({
    required this.rating,
    required this.comment,
    required this.ratedOn,
  });

  factory ReceivedRating.fromJson(Map<String, Object?> json) => ReceivedRating(
    rating: json['rating'] as int,
    comment: json['comment'] as String?,
    ratedOn: DateTime.parse(json['rated_on'] as String).toUtc(),
  );

  final int rating; // 1 to 10
  final String? comment;
  final DateTime ratedOn;
}
