import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/dio_client.dart';
import '../domain/candle.dart';

/// Timeframes supported by the backend.
enum Timeframe {
  m5('5m'),
  m15('15m'),
  m30('30m'),
  h1('1h'),
  h4('4h'),
  d1('1d');

  const Timeframe(this.wire);
  final String wire;
}

class MarketRepository {
  MarketRepository(this._dio);
  final Dio _dio;

  Future<CandlesResponse> fetchCandles({
    required String symbol,
    required Timeframe timeframe,
    int limit = 100,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/market/$symbol/candles',
      queryParameters: {
        'timeframe': timeframe.wire,
        'limit': limit,
      },
    );
    return CandlesResponse.fromJson(response.data!);
  }
}

final marketRepositoryProvider = Provider<MarketRepository>((ref) {
  return MarketRepository(ref.watch(dioProvider));
});
