import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/signal_repository.dart';
import '../domain/signal.dart';

class SignalListQuery {
  const SignalListQuery({
    this.symbol,
    this.minConfidence = 0.0,
    this.direction,
    this.limit = 50,
  });
  final String? symbol;
  final double minConfidence;
  final String? direction;
  final int limit;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SignalListQuery &&
          other.symbol == symbol &&
          other.minConfidence == minConfidence &&
          other.direction == direction &&
          other.limit == limit;

  @override
  int get hashCode =>
      Object.hash(symbol, minConfidence, direction, limit);
}

final signalsListProvider =
    FutureProvider.family<SignalList, SignalListQuery>((ref, q) {
  return ref.watch(signalRepositoryProvider).list(
        symbol: q.symbol,
        minConfidence: q.minConfidence,
        direction: q.direction,
        limit: q.limit,
      );
});

final signalByIdProvider = FutureProvider.family<Signal, int>((ref, id) {
  return ref.watch(signalRepositoryProvider).getById(id);
});
