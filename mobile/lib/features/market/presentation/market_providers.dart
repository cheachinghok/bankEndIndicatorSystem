import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/dio_client.dart';
import '../../../core/network/market_websocket.dart';
import '../data/market_repository.dart';
import '../domain/candle.dart';
import '../domain/price_tick.dart';

/// Latest candles for a symbol at a given timeframe.
final candlesProvider = FutureProvider.family<CandlesResponse, CandlesRequest>(
  (ref, req) {
    return ref.watch(marketRepositoryProvider).fetchCandles(
          symbol: req.symbol,
          timeframe: req.timeframe,
          limit: req.limit,
        );
  },
);

/// Convenience: the most recent close price for a symbol/timeframe.
final latestPriceProvider = FutureProvider.family<double?, CandlesRequest>(
  (ref, req) async {
    final data = await ref.watch(candlesProvider(req).future);
    return data.candles.isEmpty ? null : data.candles.last.close;
  },
);

/// Long-lived WebSocket for a symbol. Keyed by symbol so we can support
/// multiple symbols later — but for MVP everyone shares one XAUUSD socket.
final marketWsProvider = Provider.family<MarketWebSocket, String>((ref, symbol) {
  final config = ref.watch(appConfigProvider);
  final ws = MarketWebSocket(wsBaseUrl: config.wsBaseUrl(), symbol: symbol);
  ws.start();
  ref.onDispose(ws.dispose);
  return ws;
});

/// Stream of live price ticks for a symbol (filtered from the WS).
final livePriceStreamProvider = StreamProvider.family<PriceTick, String>((ref, symbol) {
  final ws = ref.watch(marketWsProvider(symbol));
  return ws.stream
      .where((frame) => frame['type'] == 'price')
      .map((frame) => PriceTick.fromJson(frame));
});

/// Stream of signal events for a symbol. Consumers use this to invalidate
/// caches (e.g. refresh the signals list) — payload is intentionally raw.
final signalEventStreamProvider =
    StreamProvider.family<Map<String, dynamic>, String>((ref, symbol) {
  final ws = ref.watch(marketWsProvider(symbol));
  return ws.stream.where((frame) => frame['type'] == 'signal');
});

class CandlesRequest {
  const CandlesRequest({
    required this.symbol,
    required this.timeframe,
    this.limit = 100,
  });
  final String symbol;
  final Timeframe timeframe;
  final int limit;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CandlesRequest &&
          other.symbol == symbol &&
          other.timeframe == timeframe &&
          other.limit == limit;

  @override
  int get hashCode => Object.hash(symbol, timeframe, limit);
}
