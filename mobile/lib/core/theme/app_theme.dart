import 'package:flutter/material.dart';

/// Dark, trading-desk-flavoured theme. Gold accents for the brand.
class AppTheme {
  static const _gold = Color(0xFFFFC107);
  static const _bull = Color(0xFF26A69A);
  static const _bear = Color(0xFFEF5350);
  static const _bg = Color(0xFF0E1218);
  static const _surface = Color(0xFF161B22);

  static Color bullish() => _bull;
  static Color bearish() => _bear;
  static Color neutral() => Colors.grey.shade400;

  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      colorScheme: base.colorScheme.copyWith(
        primary: _gold,
        secondary: _gold,
        surface: _surface,
        surfaceTint: Colors.transparent,
      ),
      scaffoldBackgroundColor: _bg,
      appBarTheme: const AppBarTheme(
        backgroundColor: _bg,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: base.cardTheme.copyWith(
        color: _surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.05)),
        ),
      ),
      textTheme: base.textTheme.apply(
        fontFamily: 'SF Pro Text',
        bodyColor: Colors.white,
        displayColor: Colors.white,
      ),
    );
  }
}
