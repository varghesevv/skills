/// One page of a list answered by the API: `{items, total, page, page_size}`. Lists are always
/// paged (at most 100 per page), newest or best first as each endpoint says.
class Paged<T> {
  const Paged({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory Paged.fromJson(
    Map<String, Object?> json,
    T Function(Map<String, Object?> item) parseItem,
  ) => Paged(
    items: [
      for (final item in json['items'] as List)
        parseItem(Map<String, Object?>.from(item as Map)),
    ],
    total: json['total'] as int,
    page: json['page'] as int,
    pageSize: json['page_size'] as int,
  );

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;
}
