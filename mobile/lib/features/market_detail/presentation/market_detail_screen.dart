import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/candlestick_chart.dart';
import '../../../shared/widgets/timeframe_selector.dart';
import '../../market/data/market_repository.dart';
import '../../market/domain/candle.dart';
import '../../market/presentation/market_providers.dart';

class MarketDetailScreen extends ConsumerStatefulWidget {
  const MarketDetailScreen({super.key, required this.symbol});
  final String symbol;

  @override
  ConsumerState<MarketDetailScreen> createState() => _State();
}

class _State extends ConsumerState<MarketDetailScreen> {
  Timeframe _tf = Timeframe.m15;

  CandlesRequest get _req => CandlesRequest(
        symbol: widget.symbol,
        timeframe: _tf,
        limit: 200,
      );

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(candlesProvider(_req));
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.symbol),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(candlesProvider(_req)),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (data) => _Body(
          data: data,
          selectedTf: _tf,
          onTfChanged: (tf) => setState(() => _tf = tf),
        ),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({
    required this.data,
    required this.selectedTf,
    required this.onTfChanged,
  });
  final CandlesResponse data;
  final Timeframe selectedTf;
  final ValueChanged<Timeframe> onTfChanged;

  @override
  Widget build(BuildContext context) {
    if (data.candles.isEmpty) {
      return const Center(child: Text('No candles for this timeframe.'));
    }
    final priceFmt = NumberFormat('#,##0.00');
    final last = data.candles.last;
    final first = data.candles.first;
    final change = last.close - first.close;
    final changePct = (change / first.close) * 100;
    final color = change >= 0 ? AppTheme.bullish() : AppTheme.bearish();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                priceFmt.format(last.close),
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(width: 12),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '${change >= 0 ? '+' : ''}${changePct.toStringAsFixed(2)}%',
                  style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.w600,
                    fontSize: 16,
                  ),
                ),
              ),
              const Spacer(),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: TimeframeSelector(
              selected: selectedTf, onSelected: onTfChanged),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: CandlestickChart(candles: data.candles),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _kv(context, 'O', priceFmt.format(last.open)),
                  _kv(context, 'H', priceFmt.format(last.high)),
                  _kv(context, 'L', priceFmt.format(last.low)),
                  _kv(context, 'C', priceFmt.format(last.close)),
                  _kv(context, 'V', last.volume.toStringAsFixed(0)),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _kv(BuildContext ctx, String label, String value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(ctx).textTheme.bodySmall),
          Text(value, style: Theme.of(ctx).textTheme.titleSmall),
        ],
      );
}
