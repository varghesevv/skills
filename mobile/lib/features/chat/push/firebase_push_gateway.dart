import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'push_gateway.dart';

/// Firebase Cloud Messaging. The Firebase project and its `google-services.json` are the owner's
/// and are supplied to the build, never committed (docs/android/release.md). Without them
/// `Firebase.initializeApp` fails and the app carries on with no push.
class FirebasePushGateway implements PushGateway {
  FirebasePushGateway._(this._messaging);

  final FirebaseMessaging _messaging;

  static Future<PushGateway> create() async {
    try {
      await Firebase.initializeApp();
      return FirebasePushGateway._(FirebaseMessaging.instance);
    } on Object {
      return const UnavailablePushGateway();
    }
  }

  @override
  bool get available => true;

  PushPermission _of(AuthorizationStatus status) => switch (status) {
    AuthorizationStatus.authorized ||
    AuthorizationStatus.provisional => PushPermission.granted,
    AuthorizationStatus.denied ||
    AuthorizationStatus.deniedPermanently => PushPermission.denied,
    AuthorizationStatus.notDetermined => PushPermission.unknown,
  };

  @override
  Future<PushPermission> permission() async =>
      _of((await _messaging.getNotificationSettings()).authorizationStatus);

  @override
  Future<PushPermission> requestPermission() async =>
      _of((await _messaging.requestPermission()).authorizationStatus);

  // The registration token is what the server sends to (FCM HTTP v1 `token`). The newer
  // `register()` hands out an installation id for direct sends, which is not what the server
  // uses, so the older call is kept on purpose.
  @override
  // ignore: deprecated_member_use
  Future<String?> token() => _messaging.getToken();

  @override
  // ignore: deprecated_member_use
  Stream<String> get tokenRefreshed => _messaging.onTokenRefresh;

  @override
  Stream<String> get conversationOpened => FirebaseMessaging.onMessageOpenedApp
      .map((message) => message.data['conversation_id'])
      .where((id) => id is String && id.isNotEmpty)
      .cast<String>();

  @override
  Future<String?> launchConversation() async {
    final id = (await _messaging.getInitialMessage())?.data['conversation_id'];
    return id is String && id.isNotEmpty ? id : null;
  }
}
