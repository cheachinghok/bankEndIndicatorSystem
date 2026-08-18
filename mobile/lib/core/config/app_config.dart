import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Central place for runtime configuration read from the .env file bundled
/// as an asset. Values are read once at app startup.
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.defaultSymbol,
  });

  final String apiBaseUrl;
  final String defaultSymbol;

  static AppConfig fromEnv() {
    return AppConfig(
      apiBaseUrl: dotenv.env['API_BASE_URL'] ??
          (throw StateError(
              'API_BASE_URL missing from .env — see .env.example')),
      defaultSymbol: dotenv.env['DEFAULT_SYMBOL'] ?? 'XAUUSD',
    );
  }

  /// WebSocket URL derived from the REST base URL.
  /// https://x.up.railway.app -> wss://x.up.railway.app/api/v1/ws
  String wsBaseUrl() {
    final http = apiBaseUrl.trim();
    if (http.startsWith('https://')) {
      return 'wss://${http.substring('https://'.length)}/api/v1/ws';
    }
    if (http.startsWith('http://')) {
      return 'ws://${http.substring('http://'.length)}/api/v1/ws';
    }
    throw StateError('API_BASE_URL must start with http(s)://');
  }
}
