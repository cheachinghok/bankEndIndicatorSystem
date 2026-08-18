/// A single OHLC candle.
///
/// Written as a manual immutable class rather than Freezed for MVP —
/// avoids the current analyzer/analyzer_plugin version conflict in the
/// Flutter ecosystem and keeps the model dependency-free.
class Candle {
  const Candle({
    required this.timestamp,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    this.volume = 0.0,
  });

  final DateTime timestamp;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  factory Candle.fromJson(Map<String, dynamic> json) {
    return Candle(
      timestamp: DateTime.parse(json['timestamp'] as String),
      open: (json['open'] as num).toDouble(),
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      close: (json['close'] as num).toDouble(),
      volume: json['volume'] == null ? 0.0 : (json['volume'] as num).toDouble(),
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Candle &&
          other.timestamp == timestamp &&
          other.open == open &&
          other.high == high &&
          other.low == low &&
          other.close == close &&
          other.volume == volume;

  @override
  int get hashCode =>
      Object.hash(timestamp, open, high, low, close, volume);
}

class CandlesResponse {
  const CandlesResponse({
    required this.symbol,
    required this.timeframe,
    required this.candles,
  });

  final String symbol;
  final String timeframe;
  final List<Candle> candles;

  factory CandlesResponse.fromJson(Map<String, dynamic> json) {
    final rawCandles = (json['candles'] as List<dynamic>?) ?? const [];
    return CandlesResponse(
      symbol: json['symbol'] as String,
      timeframe: json['timeframe'] as String,
      candles: rawCandles
          .map((c) => Candle.fromJson(c as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
