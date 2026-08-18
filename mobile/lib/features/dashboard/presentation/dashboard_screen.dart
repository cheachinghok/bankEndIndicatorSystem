import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/dio_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../market/data/market_repository.dart';
import '../../market/domain/candle.dart';
import '../../market/presentation/market_providers.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final symbol = ref.watch(appConfigProvider).defaultSymbol;
    final request = CandlesRequest(
      symbol: symbol,
      timeframe: Timeframe.m15,
      limit: 100,
    );
    final candlesAsync = ref.watch(candlesProvider(request));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Gold Signals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(candlesProvider(request)),
          ),
        ],
      ),
      body: candlesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _ErrorPanel(
          error: error,
          onRetry: () => ref.invalidate(candlesProvider(request)),
        ),
        data: (data) => _DashboardBody(
          response: data,
          symbol: symbol,
          onOpenChart: () => context.push('/dashboard/market/$symbol'),
        ),
      ),
    );
  }
}

class _DashboardBody extends ConsumerWidget {
  const _DashboardBody({
    required this.response,
    required this.symbol,
    required this.onOpenChart,
  });
  final CandlesResponse response;
  final String symbol;
  final VoidCallback onOpenChart;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (response.candles.isEmpty) {
      return const Center(child: Text('No candles yet — check the backend.'));
    }
    final latest = response.candles.last;
    final first = response.candles.first;
    final priceFmt = NumberFormat('#,##0.00');

    // Live price stream from WS. If no tick has arrived yet, fall back to
    // the last candle's close.
    final liveTickAsync = ref.watch(livePriceStreamProvider(symbol));
    final displayPrice = liveTickAsync.maybeWhen(
      data: (tick) => tick.mid,
      orElse: () => latest.close,
    );
    final isLive = liveTickAsync.hasValue;

    final change = displayPrice - first.close;
    final changePct = (change / first.close) * 100;
    final color = change >= 0 ? AppTheme.bullish() : AppTheme.bearish();

    return RefreshIndicator(
      onRefresh: () async {},
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: InkWell(
              onTap: onOpenChart,
              borderRadius: BorderRadius.circular(14),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          symbol,
                          style: Theme.of(context)
                              .textTheme
                              .titleLarge
                              ?.copyWith(letterSpacing: 1.0),
                        ),
                        const SizedBox(width: 8),
                        _LiveDot(isLive: isLive),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            '${change >= 0 ? '+' : ''}${changePct.toStringAsFixed(2)}%',
                            style: TextStyle(
                              color: color,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      priceFmt.format(displayPrice),
                      style: Theme.of(context).textTheme.displaySmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Text(
                          isLive
                              ? 'Live mid price'
                              : 'Timeframe: ${response.timeframe} · last close ${_fmtTime(latest.timestamp)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const Spacer(),
                        const Icon(Icons.show_chart, size: 16),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Recent candles',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  for (final c in response.candles.reversed.take(6))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          Text(
                            _fmtTime(c.timestamp),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const Spacer(),
                          Text(priceFmt.format(c.close)),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _fmtTime(DateTime ts) =>
      DateFormat('MMM d · HH:mm').format(ts.toLocal());
}

class _LiveDot extends StatefulWidget {
  const _LiveDot({required this.isLive});
  final bool isLive;

  @override
  State<_LiveDot> createState() => _LiveDotState();
}

class _LiveDotState extends State<_LiveDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl =
      AnimationController(vsync: this, duration: const Duration(seconds: 1))
        ..repeat(reverse: true);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isLive) {
      return const _StaticDot(color: Colors.grey);
    }
    return FadeTransition(
      opacity: Tween(begin: 0.35, end: 1.0).animate(_ctl),
      child: _StaticDot(color: AppTheme.bullish()),
    );
  }
}

class _StaticDot extends StatelessWidget {
  const _StaticDot({required this.color});
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.error, required this.onRetry});
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.error_outline, size: 48),
          const SizedBox(height: 12),
          Text('Could not load market data',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text('$error',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
