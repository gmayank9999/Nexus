import 'package:flutter/material.dart';

abstract final class NexusTheme {
  static const _primary = Color(0xFF8A7DFF);
  static const _secondary = Color(0xFF42D6FF);
  static const _background = Color(0xFF090B12);

  static ThemeData get dark {
    final scheme = ColorScheme.fromSeed(
      seedColor: _primary,
      brightness: Brightness.dark,
      primary: _primary,
      secondary: _secondary,
      surface: _background,
      error: const Color(0xFFFF6B7A),
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: _background,
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: const Color(0xFF11141E),
        indicatorColor: _primary.withValues(alpha: 0.18),
        height: 72,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.45),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
      ),
    );
  }
}
