import '../../core/api/api_client.dart';
import '../../core/api/paged.dart';
import '../../core/api/parse.dart';
import 'search_models.dart';

/// Results come twelve at a time, as on the web.
const searchPageSize = 12;

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
}
