import 'package:intl/intl.dart';

/// "5 Nov 2026, 9:00 AM": a moment in the phone's own time zone and locale.
String formatPeriodTime(DateTime time) =>
    DateFormat.yMMMd().add_jm().format(time.toLocal());
