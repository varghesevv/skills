import '../terminology/terms.dart';
import 'strings_en.dart';

/// Looks up a text by key, resolves the role words from the server's [Terms], then fills the
/// caller's `{name}` values. English only for now; texts stay in one place so a language can be
/// added.
///
/// The order matters: values come last and in a single pass, so something a person typed (a
/// display name that happens to contain `{organisation}`) is shown exactly as typed.
class AppText {
  const AppText(this.terms);

  final Terms terms;

  static final _placeholder = RegExp(r'\{([A-Za-z_]+)\}');

  String call(String key, [Map<String, String> values = const {}]) {
    final template = stringsEn[key];
    if (template == null) throw StateError('Unknown text: $key');
    return terms
        .apply(template)
        .replaceAllMapped(
          _placeholder,
          (match) => values[match.group(1)] ?? match.group(0)!,
        );
  }
}
