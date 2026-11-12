import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Asks the person for a date and a time. Returns null when they cancel.
typedef PickDateTime = Future<DateTime?> Function(
  BuildContext context,
  DateTime? initial,
);

/// The system date picker followed by the system time picker. Kept behind a provider so tests
/// can answer without driving the dial.
Future<DateTime?> pickDateTimeWithSystemPickers(
  BuildContext context,
  DateTime? initial,
) async {
  final start = (initial ?? DateTime.now()).toLocal();
  final date = await showDatePicker(
    context: context,
    initialDate: start,
    firstDate: DateTime(start.year - 5),
    lastDate: DateTime(start.year + 10),
  );
  if (date == null || !context.mounted) return null;
  final time = await showTimePicker(
    context: context,
    initialTime: TimeOfDay.fromDateTime(start),
  );
  if (time == null) return null;
  return DateTime(date.year, date.month, date.day, time.hour, time.minute);
}

final dateTimePickerProvider = Provider<PickDateTime>(
  (ref) => pickDateTimeWithSystemPickers,
);
