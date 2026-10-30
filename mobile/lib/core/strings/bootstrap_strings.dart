/// Texts shown **before** the server's configuration has loaded.
///
/// At that point the role words are not known (they come from the server), so these texts are
/// fixed English and contain no role word. They are kept together here, away from the screens, so
/// they can be translated in one step when a second language is added.
class BootstrapStrings {
  const BootstrapStrings._();

  static const appName = 'Skills';
  static const tryAgain = 'Try again';

  /// The configuration request got a 404 or an answer of the wrong shape. That means the server
  /// is older than this app needs, or the app points at the wrong address (a proxy or another
  /// site also answers 404), so the text names both without blaming either.
  static const serverMismatch =
      'The server did not answer the way this version of the app expects. '
      'It may need updating, or the server address may be wrong. '
      'Ask the administrator, then try again.';
}
