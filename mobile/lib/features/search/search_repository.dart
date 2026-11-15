import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/api/paged.dart';
import '../../core/api/parse.dart';
import 'provider_models.dart';
import 'search_models.dart';

/// Results come twelve at a time, as on the web.
const searchPageSize = 12;

/// The ratings given are listed ten at a time, as on the web.
const givenPageSize = 10;

class SearchRepository {
  SearchRepository(this._api);

  final ApiClient _api;

  Future<Paged<SearchResultItem>> search(
    SearchFilters filters, {
    required int page,
  }) async => parseResponse(
    await _api.get(
      '/search/freelancers',
      query: {...filters.toQuery(), 'page': page, 'page_size': searchPageSize},
    ),
    (json) => Paged.fromJson(json, SearchResultItem.fromJson),
  );

  /// One page of the ratings the caller gave, newest first. The path keeps its older name.
  Future<Paged<GivenRating>> givenRatings({required int page}) async =>
      parseResponse(
        await _api.get(
          '/workhosts/me/ratings',
          query: {'page': page, 'page_size': givenPageSize},
        ),
        (json) => Paged.fromJson(json, GivenRating.fromJson),
      );

  Future<ProviderPublic> provider(String id) async => parseResponse(
    await _api.get('/freelancers/$id'),
    ProviderPublic.fromJson,
  );

  /// The only call that returns a mobile number. Every call is recorded and rate limited. The
  /// number is handed to the caller and kept nowhere else.
  Future<String> reveal(
    String id, {
    List<String> searchedSkills = const [],
  }) async {
    final data = await _api.post(
      '/freelancers/$id/reveal-mobile',
      body: {
        'channel': 'dial',
        'source': 'detail',
        'searched_skills': searchedSkills.take(10).toList(),
      },
    );
    if (data is! Map || data['mobile_number'] is! String) {
      throw const ApiException.badResponse();
    }
    return data['mobile_number'] as String;
  }

  Future<GivenRating> rate(
    String providerId,
    int rating,
    String? comment,
  ) async => parseResponse(
    await _api.post(
      '/ratings',
      body: {'provider_id': providerId, 'rating': rating, 'comment': comment},
    ),
    GivenRating.fromJson,
  );

  Future<GivenRating> changeRating(
    String id,
    int rating,
    String? comment,
  ) async => parseResponse(
    await _api.put(
      '/ratings/$id',
      body: {'rating': rating, 'comment': comment},
    ),
    GivenRating.fromJson,
  );
}
