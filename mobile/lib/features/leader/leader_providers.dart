import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

/// Opens the phone's dialler with a number. It only opens it; nothing is dialled. A provider so
/// tests can replace it.
final dialerProvider = Provider<Future<bool> Function(String number)>((ref) {
  return (number) {
    // Only digits and a leading plus go into the address.
    final digits = number.replaceAll(RegExp(r'[^\d+]'), '');
    return launchUrl(Uri(scheme: 'tel', path: digits));
  };
});
