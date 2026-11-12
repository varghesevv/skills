/// A period when the freelancer cannot work (`/freelancers/me/unavailability`). Times travel as
/// ISO 8601 with a time zone; they are kept in UTC and shown in the phone's local time.
class Unavailability {
  const Unavailability({
    required this.id,
    required this.from,
    required this.to,
  });

  factory Unavailability.fromJson(Map<String, Object?> json) => Unavailability(
    id: json['id'] as String,
    from: DateTime.parse(json['unavailable_from'] as String).toUtc(),
    to: DateTime.parse(json['unavailable_to'] as String).toUtc(),
  );

  final String id;
  final DateTime from;
  final DateTime to;
}

/// What the form sends for a new or changed period.
Map<String, Object?> periodBody(DateTime from, DateTime to) => {
  'unavailable_from': from.toUtc().toIso8601String(),
  'unavailable_to': to.toUtc().toIso8601String(),
};
