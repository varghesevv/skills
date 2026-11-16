import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// What the app remembers about notifications on this phone.
abstract class PushPreferences {
  /// Whether the person has been asked to allow notifications (the system's question is only
  /// worth showing once).
  Future<bool> asked();

  Future<void> markAsked();
}

class SecurePushPreferences implements PushPreferences {
  SecurePushPreferences([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'skills.push_asked';

  final FlutterSecureStorage _storage;

  @override
  Future<bool> asked() async {
    try {
      return await _storage.read(key: _key) == '1';
    } on Exception {
      return false;
    }
  }

  @override
  Future<void> markAsked() async {
    try {
      await _storage.write(key: _key, value: '1');
    } on Exception {
      // Asking again next time is the worst that can happen.
    }
  }
}
