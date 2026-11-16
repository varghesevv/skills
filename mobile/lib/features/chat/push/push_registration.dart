import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router.dart';
import '../../../core/session/session_controller.dart';
import '../chat_paths.dart';
import '../chat_providers.dart';
import 'firebase_push_gateway.dart';
import 'push_gateway.dart';
import 'push_preferences.dart';

/// The phone's push service. A provider so that tests (and builds without Firebase) can replace
/// it.
final pushGatewayProvider = FutureProvider<PushGateway>(
  (ref) => FirebasePushGateway.create(),
);

final pushPreferencesProvider = Provider<PushPreferences>(
  (ref) => SecurePushPreferences(),
);

/// Tells the server which phone to send this person's notifications to, and forgets it at
/// sign-out. The push carries no text (only "You have a new message" and the conversation id).
class PushRegistration {
  PushRegistration(this._ref);

  final Ref _ref;
  String? _deviceId;
  String? _registeredToken;
  Future<void>? _syncing;
  bool _again = false;

  Future<PushGateway> _gateway() => _ref.read(pushGatewayProvider.future);

  /// Registers this phone's address when notifications are allowed. Calls that overlap share
  /// one run; any failure is left for the next start (a push is never worth an error on screen).
  Future<void> sync() {
    final running = _syncing;
    if (running != null) {
      // Asked again while a run is under way (a new address arrived): run once more after it,
      // so the newest address is the one the server ends with.
      _again = true;
      return running;
    }
    return _syncing = _syncLoop().whenComplete(() => _syncing = null);
  }

  Future<void> _syncLoop() async {
    do {
      _again = false;
      await _sync();
    } while (_again);
  }

  Future<void> _sync() async {
    try {
      final gateway = await _gateway();
      if (!gateway.available) return;
      if (await gateway.permission() != PushPermission.granted) return;
      final token = await gateway.token();
      if (token == null || token == _registeredToken) return;
      _deviceId = await _ref.read(chatRepositoryProvider).registerDevice(token);
      _registeredToken = token;
    } on Object {
      // Tried again at the next start and at the next new address.
    }
  }

  /// Asks the person to allow notifications, once, when they first look at their messages (not
  /// at launch, when they have no reason yet to say yes).
  Future<void> offerPermission() async {
    try {
      final gateway = await _gateway();
      if (!gateway.available) return;
      final preferences = _ref.read(pushPreferencesProvider);
      if (await preferences.asked()) return;
      if (await gateway.permission() != PushPermission.unknown) {
        await preferences.markAsked();
        return;
      }
      await preferences.markAsked();
      if (await gateway.requestPermission() == PushPermission.granted) {
        await sync();
      }
    } on Object {
      // The question can be put again next time.
    }
  }

  /// Stops notifications for this phone (sign-out). A failure is ignored: the person is signed
  /// out either way, and a new sign-in on this phone replaces the address.
  Future<void> unregister() async {
    final id = _deviceId;
    _deviceId = null;
    _registeredToken = null;
    if (id == null) return;
    try {
      // Never hold the sign-out for long: a phone that cannot be reached is forgotten later,
      // when the next person to sign in on it registers the address.
      await _ref
          .read(chatRepositoryProvider)
          .forgetDevice(id)
          .timeout(const Duration(seconds: 5));
    } on Object {
      // See above.
    }
  }
}

/// One registration per signed-in person: when the session ends, in any way, and another person
/// signs in, the state of the first is gone and the phone is registered again for the second.
final pushRegistrationProvider = Provider<PushRegistration>((ref) {
  ref.watch(personProvider.select((person) => person?.id));
  return PushRegistration(ref);
});

/// Asks for permission when a messages screen is opened (once per phone).
final pushOfferProvider = FutureProvider.autoDispose<void>(
  (ref) => ref.read(pushRegistrationProvider).offerPermission(),
);

/// Registers the phone while a member is signed in, and opens the conversation of a tapped
/// notification. Watched by the member's home page next to `chatLiveProvider`.
final pushLiveProvider = Provider.autoDispose<void>((ref) {
  final registration = ref.read(pushRegistrationProvider);
  final subscriptions = <StreamSubscription<String>>[];
  var disposed = false;

  void open(String id) {
    if (!disposed) ref.read(routerProvider).push(chatThread(id));
  }

  unawaited(() async {
    try {
      final gateway = await ref.read(pushGatewayProvider.future);
      if (disposed || !gateway.available) return;
      subscriptions
        ..add(gateway.tokenRefreshed.listen((_) => registration.sync()))
        ..add(gateway.conversationOpened.listen(open));
      await registration.sync();
      final launched = await gateway.launchConversation();
      if (launched != null) open(launched);
    } on Object {
      // No push; the app works without it.
    }
  }());
  ref.onDispose(() {
    disposed = true;
    for (final subscription in subscriptions) {
      unawaited(subscription.cancel());
    }
  });
});
