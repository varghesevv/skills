import 'package:intl/intl.dart';

/// "5 Nov 2026, 9:00 AM": a moment in the phone's own time zone and locale.
String formatPeriodTime(DateTime time) =>
    DateFormat.yMMMd().add_jm().format(time.toLocal());

/// "5 Nov 2026": a day in the phone's own time zone and locale.
String formatDay(DateTime time) => DateFormat.yMMMd().format(time.toLocal());
