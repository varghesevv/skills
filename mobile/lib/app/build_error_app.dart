import 'package:flutter/material.dart';

/// Shown instead of the app when a release build was made without its build settings. It names
/// the missing settings only; it never shows values.
class BuildErrorApp extends StatelessWidget {
  const BuildErrorApp({super.key, required this.problems});

  final List<String> problems;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Text(
                'This build is not configured. Missing or invalid: ${problems.join(', ')}.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
