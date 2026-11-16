import 'dart:async';

/// Whether the person has let the app show notifications.
enum PushPermission {
  /// Not asked yet.
  unknown,
  granted,
  denied,
}

/// What the app needs from the phone's push service (Firebase Cloud Messaging on Android). The
/// rest of the app talks to this, so everything works, and is tested, without Firebase: a build
/// without the owner's Firebase files simply has no push ([UnavailablePushGateway]).
abstract class PushGateway {
  /// False when there is no push service in this build or on this phone.
  bool get available;

  Future<PushPermission> permission();

  /// Shows the system's question; returns the answer.
  Future<PushPermission> requestPermission();

  /// This phone's address for the server, or null when there is none yet.
  Future<String?> token();

  /// The service gave this phone a new address.
  Stream<String> get tokenRefreshed;

  /// The person tapped a notification while the app was running: the conversation it is about.
  Stream<String> get conversationOpened;

  /// The notification whose tap started the app, if that is how it started (once).
  Future<String?> launchConversation();
}

/// No push in this build: no Firebase files were supplied, or the phone has no Google services.
class UnavailablePushGateway implements PushGateway {
  const UnavailablePushGateway();

  @override
  bool get available => false;

  @override
  Future<PushPermission> permission() async => PushPermission.denied;

  @override
  Future<PushPermission> requestPermission() async => PushPermission.denied;

  @override
  Future<String?> token() async => null;

  @override
  Stream<String> get tokenRefreshed => const Stream.empty();

  @override
  Stream<String> get conversationOpened => const Stream.empty();

  @override
  Future<String?> launchConversation() async => null;
}
