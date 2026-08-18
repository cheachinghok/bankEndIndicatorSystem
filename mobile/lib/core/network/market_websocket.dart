import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Manages a single WebSocket to `/api/v1/ws/market/{symbol}`, reconnecting
/// with exponential backoff whenever the connection drops.
///
/// Exposes a broadcast [Stream] of parsed JSON frames so multiple listeners
/// (Dashboard, Signals, etc.) share one socket. Cancel the returned
/// StreamSubscription — no explicit close needed if you don't hold a
/// reference beyond the stream itself; call [dispose] to tear down cleanly.
class MarketWebSocket {
  MarketWebSocket({required this.wsBaseUrl, required this.symbol});

  final String wsBaseUrl; // e.g. wss://x.up.railway.app/api/v1/ws
  final String symbol;

  static const _minBackoff = Duration(seconds: 1);
  static const _maxBackoff = Duration(seconds: 30);

  final _controller = StreamController<Map<String, dynamic>>.broadcast();
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSub;
  Duration _backoff = _minBackoff;
  bool _closed = false;

  /// Broadcast stream of parsed JSON frames.
  Stream<Map<String, dynamic>> get stream => _controller.stream;

  void start() {
    if (_closed) return;
    _connect();
  }

  Future<void> dispose() async {
    _closed = true;
    await _channelSub?.cancel();
    await _channel?.sink.close();
    await _controller.close();
  }

  Uri _uri() => Uri.parse('$wsBaseUrl/market/$symbol');

  void _connect() {
    if (_closed) return;
    try {
      final channel = WebSocketChannel.connect(_uri());
      _channel = channel;
      _channelSub = channel.stream.listen(
        _onMessage,
        onError: (Object err, _) {
          if (kDebugMode) debugPrint('[MarketWS] error: $err');
          _scheduleReconnect();
        },
        onDone: () {
          if (kDebugMode) debugPrint('[MarketWS] closed by server');
          _scheduleReconnect();
        },
        cancelOnError: true,
      );
      // Successful open resets backoff — reset after the first tick arrives
      // so a broken server that accepts+closes doesn't keep spamming quickly.
    } catch (e) {
      if (kDebugMode) debugPrint('[MarketWS] connect failed: $e');
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic data) {
    if (_closed) return;
    _backoff = _minBackoff; // healthy stream → reset backoff
    try {
      final str = data is String ? data : (data as List<int>).toString();
      final obj = jsonDecode(str) as Map<String, dynamic>;
      _controller.add(obj);
    } catch (_) {
      // Malformed frame — drop it silently.
    }
  }

  void _scheduleReconnect() {
    if (_closed) return;
    _channelSub?.cancel();
    _channelSub = null;
    _channel = null;
    final delay = _backoff;
    _backoff = Duration(
      milliseconds: (_backoff.inMilliseconds * 2).clamp(
        _minBackoff.inMilliseconds,
        _maxBackoff.inMilliseconds,
      ),
    );
    if (kDebugMode) debugPrint('[MarketWS] reconnecting in ${delay.inSeconds}s');
    Timer(delay, _connect);
  }
}
