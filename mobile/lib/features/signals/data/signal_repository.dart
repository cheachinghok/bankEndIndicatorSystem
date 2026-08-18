import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/dio_client.dart';
import '../domain/signal.dart';

class SignalRepository {
  SignalRepository(this._dio);
  final Dio _dio;

  Future<SignalList> list({
    String? symbol,
    double minConfidence = 0.0,
    String? direction, // BUY | SELL | WAIT
    int limit = 50,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/signals',
      queryParameters: {
        if (symbol != null) 'symbol': symbol,
        'min_confidence': minConfidence,
        if (direction != null) 'direction': direction,
        'limit': limit,
      },
    );
    return SignalList.fromJson(response.data!);
  }

  Future<Signal> getById(int id) async {
    final response = await _dio.get<Map<String, dynamic>>('/signals/$id');
    return Signal.fromJson(response.data!);
  }
}

final signalRepositoryProvider = Provider<SignalRepository>((ref) {
  return SignalRepository(ref.watch(dioProvider));
});
