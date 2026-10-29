/// The words for the three kinds of people, as served by `GET /api/v1/app/config`.
///
/// The app carries no copy of the word profiles: every role word comes from the server, so the
/// app shows the same words as the web for the same installation. Port of
/// `frontend/src/terminology/terms.ts`.
class Terms {
  const Terms(this._words);

  final Map<String, String> _words;

  /// One word or address slug, for example `term('organisation_path')`.
  String term(String key) {
    final value = _words[key];
    if (value == null) throw StateError('Unknown term: $key');
    return value;
  }

  static final _token = RegExp(r'\{(A_|a_)?([A-Za-z]+)\}');
  static const _kinds = {'organisation', 'workhost', 'freelancer'};

  /// Replaces the term tokens in a text:
  /// `{organisation}` gives the word in lower case, `{Organisation}` as written,
  /// `{organisations}` the plural, `{a_organisation}` "a church" or "an organisation" and
  /// `{A_organisation}` the same with a capital. Other `{names}` are left alone.
  String apply(String text) {
    return text.replaceAllMapped(_token, (match) {
      final prefix = match.group(1);
      final name = match.group(2)!;
      final lower = _lowerFirst(name);
      final base = lower.endsWith('s')
          ? lower.substring(0, lower.length - 1)
          : lower;
      if (!_kinds.contains(base) || !_words.containsKey(lower)) {
        return match.group(0)!;
      }
      final written = term(lower);
      final capital = name[0] == name[0].toUpperCase();
      if (prefix != null) {
        final word = _lowerFirst(written);
        final phrase = '${_article(word)} $word';
        return prefix == 'A_' ? _upperFirst(phrase) : phrase;
      }
      return capital ? written : _lowerFirst(written);
    });
  }

  static String _article(String word) =>
      RegExp(r'^[aeiou]', caseSensitive: false).hasMatch(word) ? 'an' : 'a';
  static String _lowerFirst(String word) =>
      word.isEmpty ? word : word[0].toLowerCase() + word.substring(1);
  static String _upperFirst(String word) =>
      word.isEmpty ? word : word[0].toUpperCase() + word.substring(1);
}
