import '../../core/auth/person_me.dart';

/// The ways the results can be ordered (`sort` of the API).
enum SearchSort {
  newest,
  rating,
  rate;

  String get wire => name;
}

/// What the person asked for. Immutable; every change builds a new value, and only what differs
/// from the default goes into the query, as on the web.
class SearchFilters {
  const SearchFilters({
    this.name = '',
    this.skills = const [],
    this.matchAll = false,
    this.skillLevel = '',
    this.languages = const [],
    this.timings = const [],
    this.nativity = const [],
    this.maxRate = '',
    this.currency = '',
    this.negotiable = false,
    this.availableFrom,
    this.availableTo,
    this.minRating = '',
    this.churchId = '',
    this.homeGroupId = '',
    this.sort = SearchSort.newest,
  });

  final String name;
  final List<String> skills;
  final bool matchAll;
  final String skillLevel;
  final List<String> languages;
  final List<String> timings;
  final List<String> nativity;
  final String maxRate;
  final String currency;
  final bool negotiable;
  final DateTime? availableFrom;
  final DateTime? availableTo;
  final String minRating;
  final String churchId;
  final String homeGroupId;
  final SearchSort sort;

  SearchFilters copyWith({
    String? name,
    List<String>? skills,
    bool? matchAll,
    String? skillLevel,
    List<String>? languages,
    List<String>? timings,
    List<String>? nativity,
    String? maxRate,
    String? currency,
    bool? negotiable,
    Object? availableFrom = _keep,
    Object? availableTo = _keep,
    String? minRating,
    String? churchId,
    String? homeGroupId,
    SearchSort? sort,
  }) => SearchFilters(
    name: name ?? this.name,
    skills: skills ?? this.skills,
    matchAll: matchAll ?? this.matchAll,
    skillLevel: skillLevel ?? this.skillLevel,
    languages: languages ?? this.languages,
    timings: timings ?? this.timings,
    nativity: nativity ?? this.nativity,
    maxRate: maxRate ?? this.maxRate,
    currency: currency ?? this.currency,
    negotiable: negotiable ?? this.negotiable,
    availableFrom: identical(availableFrom, _keep)
        ? this.availableFrom
        : availableFrom as DateTime?,
    availableTo: identical(availableTo, _keep)
        ? this.availableTo
        : availableTo as DateTime?,
    minRating: minRating ?? this.minRating,
    churchId: churchId ?? this.churchId,
    homeGroupId: homeGroupId ?? this.homeGroupId,
    sort: sort ?? this.sort,
  );

  static const _keep = Object();

  /// How many filters are on (the sort and the name are shown apart).
  int get activeCount =>
      skills.length +
      languages.length +
      timings.length +
      nativity.length +
      [
        skillLevel,
        maxRate,
        negotiable,
        availableFrom,
        minRating,
        churchId,
        homeGroupId,
      ].where((v) => v != '' && v != false && v != null).length;

  /// The query of the API; a list repeats its key.
  Map<String, Object> toQuery() => {
    if (name.trim().isNotEmpty) 'name': name.trim(),
    if (skills.isNotEmpty) 'skill': skills,
    if (skills.length > 1 && matchAll) 'skill_match': 'all',
    if (skillLevel.isNotEmpty) 'skill_level': skillLevel,
    if (languages.isNotEmpty) 'language': languages,
    if (timings.isNotEmpty) 'timing': timings,
    if (nativity.isNotEmpty) 'nativity': nativity,
    if (maxRate.trim().isNotEmpty) 'max_rate': maxRate.trim(),
    if (currency.trim().isNotEmpty) 'currency': currency.trim().toUpperCase(),
    if (negotiable) 'negotiable': 'true',
    if (availableFrom != null && availableTo != null) ...{
      'available_from': availableFrom!.toUtc().toIso8601String(),
      'available_to': availableTo!.toUtc().toIso8601String(),
    },
    if (minRating.isNotEmpty) 'min_rating': minRating,
    if (churchId.isNotEmpty) 'church_id': churchId,
    if (homeGroupId.isNotEmpty) 'home_group_id': homeGroupId,
    if (sort != SearchSort.newest) 'sort': sort.wire,
  };
}

class SearchSkill {
  const SearchSkill({required this.name, this.level});

  factory SearchSkill.fromJson(Map<String, Object?> json) => SearchSkill(
    name: json['name'] as String,
    level: json['level'] as String?,
  );

  final String name;
  final String? level;
}

/// A provider in the results. Never a mobile number or an address: the number comes from the
/// Reveal endpoint only.
class SearchResultItem {
  const SearchResultItem({
    required this.id,
    required this.fullName,
    required this.church,
    required this.homeGroup,
    required this.nationality,
    required this.primaryLanguage,
    required this.ratePerHour,
    required this.rateCurrency,
    required this.isRateNegotiable,
    required this.averageRating,
    required this.ratingCount,
    required this.skills,
    required this.languages,
  });

  factory SearchResultItem.fromJson(Map<String, Object?> json) =>
      SearchResultItem(
        id: json['id'] as String,
        fullName: json['full_name'] as String?,
        church: NamedRef.fromJson(
          Map<String, Object?>.from(json['church'] as Map),
        ),
        homeGroup: NamedRef.fromJson(
          Map<String, Object?>.from(json['home_group'] as Map),
        ),
        nationality: json['nationality'] as String?,
        primaryLanguage: json['primary_language'] as String?,
        ratePerHour: (json['rate_per_hour'] as num?)?.toDouble(),
        rateCurrency: json['rate_currency'] as String?,
        isRateNegotiable: (json['is_rate_negotiable'] as bool?) ?? false,
        averageRating: (json['average_rating'] as num?)?.toDouble(),
        ratingCount: json['rating_count'] as int,
        skills: [
          for (final s in json['skills'] as List)
            SearchSkill.fromJson(Map<String, Object?>.from(s as Map)),
        ],
        languages: [for (final l in json['languages'] as List) l as String],
      );

  final String id;
  final String? fullName;
  final NamedRef church;
  final NamedRef homeGroup;
  final String? nationality;
  final String? primaryLanguage;
  final double? ratePerHour;
  final String? rateCurrency;
  final bool isRateNegotiable;
  final double? averageRating;
  final int ratingCount;
  final List<SearchSkill> skills;
  final List<String> languages;
}
