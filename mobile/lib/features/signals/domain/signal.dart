/// A trading signal — matches the backend's SignalOut Pydantic model.
///
/// `direction` is the wire value ("BUY" | "SELL" | "WAIT"); the enum is
/// derived on-demand via the [directionEnum] getter so we never crash on
/// an unknown value.
enum SignalDirection {
  buy,
  sell,
  wait,
  unknown;

  static SignalDirection fromWire(String value) {
    switch (value.toUpperCase()) {
      case 'BUY':
        return SignalDirection.buy;
      case 'SELL':
        return SignalDirection.sell;
      case 'WAIT':
        return SignalDirection.wait;
      default:
        return SignalDirection.unknown;
    }
  }

  String get label => switch (this) {
        SignalDirection.buy => 'BUY',
        SignalDirection.sell => 'SELL',
        SignalDirection.wait => 'WAIT',
        SignalDirection.unknown => '—',
      };
}

class Signal {
  const Signal({
    required this.id,
    required this.symbol,
    required this.timeframe,
    required this.direction,
    required this.confidence,
    required this.entry,
    required this.stopLoss,
    required this.takeProfit1,
    required this.takeProfit2,
    required this.riskReward,
    required this.breakdown,
    required this.reasons,
    required this.warnings,
    required this.generatedAt,
  });

  final int id;
  final String symbol;
  final String timeframe;
  final String direction; // wire string
  final double confidence;
  final double? entry;
  final double? stopLoss;
  final double? takeProfit1;
  final double? takeProfit2;
  final double? riskReward;
  final Map<String, num> breakdown;
  final List<String> reasons;
  final List<String> warnings;
  final DateTime generatedAt;

  SignalDirection get directionEnum => SignalDirection.fromWire(direction);

  bool get isActionable =>
      directionEnum == SignalDirection.buy || directionEnum == SignalDirection.sell;

  factory Signal.fromJson(Map<String, dynamic> json) {
    final rawBreakdown = json['breakdown'] as Map<String, dynamic>? ?? const {};
    return Signal(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      timeframe: json['timeframe'] as String,
      direction: json['direction'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      entry: (json['entry'] as num?)?.toDouble(),
      stopLoss: (json['stop_loss'] as num?)?.toDouble(),
      takeProfit1: (json['take_profit_1'] as num?)?.toDouble(),
      takeProfit2: (json['take_profit_2'] as num?)?.toDouble(),
      riskReward: (json['risk_reward'] as num?)?.toDouble(),
      breakdown: rawBreakdown.map((k, v) => MapEntry(k, v as num)),
      reasons: ((json['reasons'] as List<dynamic>?) ?? const [])
          .map((e) => e as String)
          .toList(growable: false),
      warnings: ((json['warnings'] as List<dynamic>?) ?? const [])
          .map((e) => e as String)
          .toList(growable: false),
      generatedAt: DateTime.parse(json['generated_at'] as String),
    );
  }
}

class SignalList {
  const SignalList({required this.count, required this.signals});

  final int count;
  final List<Signal> signals;

  factory SignalList.fromJson(Map<String, dynamic> json) {
    final raw = (json['signals'] as List<dynamic>?) ?? const [];
    return SignalList(
      count: json['count'] as int? ?? raw.length,
      signals: raw
          .map((s) => Signal.fromJson(s as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
