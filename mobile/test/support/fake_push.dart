import 'dart:async';

import 'package:skills_app/features/chat/push/push_gateway.dart';
import 'package:skills_app/features/chat/push/push_preferences.dart';

/// A stand-in for the phone's push service. Nothing real is contacted.
class FakePushGateway implements PushGateway {
  FakePushGateway({
    this.state = PushPermission.unknown,
    this.answer = PushPermission.granted,
    this.address = 'device-address-1',
    this.launch,
  });

  /// What the system says now; [answer] is what the person will answer when asked.
  PushPermission state;
  final PushPermission answer;
  String? address;
  String? launch;
  int asked = 0;
  final refreshed = StreamController<String>.broadcast();
  final opened = StreamController<String>.broadcast();

  @override
  bool get available => true;

  @override
  Future<PushPermission> permission() async => state;

  @override
  Future<PushPermission> requestPermission() async {
    asked++;
    state = answer;
    return state;
  }

  @override
  Future<String?> token() async => address;

  @override
  Stream<String> get tokenRefreshed => refreshed.stream;

  @override
  Stream<String> get conversationOpened => opened.stream;

  @override
  Future<String?> launchConversation() async => launch;
}

class MemoryPushPreferences implements PushPreferences {
  MemoryPushPreferences({this.wasAsked = false});

  bool wasAsked;

  @override
  Future<bool> asked() async => wasAsked;

  @override
  Future<void> markAsked() async => wasAsked = true;
}
