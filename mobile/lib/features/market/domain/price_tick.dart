/// A single live price observation, coming from the /ws/market/{symbol}
/// WebSocket as `{"type":"price","symbol":"XAUUSD",...}`.
class PriceTick {
  const PriceTick({
    required this.symbol,
    required this.timestamp,
    required this.bid,
    required this.ask,
    required this.mid,
    this.tradeable = true,
  });

  final String symbol;
  final DateTime timestamp;
  final double bid;
  final double ask;
  final double mid;
  final bool tradeable;

  factory PriceTick.fromJson(Map<String, dynamic> json) {
    return PriceTick(
      symbol: json['symbol'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      bid: (json['bid'] as num).toDouble(),
      ask: (json['ask'] as num).toDouble(),
      mid: (json['mid'] as num?)?.toDouble() ??
          (((json['bid'] as num).toDouble() + (json['ask'] as num).toDouble()) / 2),
      tradeable: json['tradeable'] as bool? ?? true,
    );
  }
}
