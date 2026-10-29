import 'package:flutter/material.dart';

const _seed = Color(0xFF1F5FA8);

ThemeData buildTheme(Brightness brightness) {
  return ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: _seed, brightness: brightness),
    // Tap targets of at least 48 dp on every platform (plan section 1, accessibility).
    materialTapTargetSize: MaterialTapTargetSize.padded,
    visualDensity: VisualDensity.standard,
  );
}
