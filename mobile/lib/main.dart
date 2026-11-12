import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'app/app.dart';
import 'app/build_error_app.dart';
import 'core/env.dart';

void main() {
  // A release build without its settings must not run: it would skip the update check or call
  // no server. Debug and test builds may leave the settings out.
  final problems = Env.problems();
  if (kReleaseMode && problems.isNotEmpty) {
    runApp(BuildErrorApp(problems: problems));
    return;
  }
  runApp(appRoot());
}
