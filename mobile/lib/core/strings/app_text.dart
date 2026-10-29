import '../terminology/terms.dart';
import 'strings_en.dart';

/// Looks up a text by key, fills `{name}` values, then resolves the role words from the
/// server's [Terms]. English only for now; texts stay in one place so a language can be added.
class AppText {
  const AppText(this.terms);

  final Terms terms;

  String call(String key, [Map<String, String> values = const {}]) {
    var text = stringsEn[key];
    if (text == null) throw StateError('Unknown text: $key');
    values.forEach((name, value) => text = text!.replaceAll('{$name}', value));
    return terms.apply(text!);
  }
}
