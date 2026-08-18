import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/dio_client.dart';
import '../../../features/market/presentation/market_providers.dart';
import '../../../shared/widgets/direction_badge.dart';
import '../domain/signal.dart';
import 'signal_providers.dart';

class SignalsListScreen extends ConsumerWidget {
  const SignalsListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final symbol = ref.watch(appConfigProvider).defaultSymbol;
    final query = SignalListQuery(symbol: symbol, limit: 50);
    final async = ref.watch(signalsListProvider(query));

    // Auto-refresh the list when a new signal frame arrives on the WS.
    ref.listen(signalEventStreamProvider(symbol), (_, __) {
      ref.invalidate(signalsListProvider(query));
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Signals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(signalsListProvider(query)),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _errorPanel(context, e, () => ref.invalidate(signalsListProvider(query))),
        data: (data) => _SignalListBody(list: data),
      ),
    );
  }

  Widget _errorPanel(BuildContext context, Object err, VoidCallback onRetry) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48),
          const SizedBox(height: 12),
          Text('Could not load signals',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text('$err',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center),
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

class _SignalListBody extends StatelessWidget {
  const _SignalListBody({required this.list});
  final SignalList list;

  @override
  Widget build(BuildContext context) {
    if (list.signals.isEmpty) {
      return const _EmptyState();
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: list.signals.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, i) => _SignalRow(signal: list.signals[i]),
    );
  }
}

class _SignalRow extends StatelessWidget {
  const _SignalRow({required this.signal});
  final Signal signal;

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##0.00');
    return Card(
      child: InkWell(
        onTap: () => context.push('/signals/${signal.id}'),
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(signal.symbol,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(width: 8),
                  Text('· ${signal.timeframe}',
                      style: Theme.of(context).textTheme.bodySmall),
                  const Spacer(),
                  DirectionBadge(direction: signal.directionEnum),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(
                    'Confidence ${signal.confidence.toStringAsFixed(0)}',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(width: 12),
                  if (signal.entry != null)
                    Text(
                      '@ ${priceFmt.format(signal.entry)}',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  const Spacer(),
                  Text(
                    _relTime(signal.generatedAt),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _relTime(DateTime ts) {
    final delta = DateTime.now().difference(ts);
    if (delta.inSeconds < 60) return '${delta.inSeconds}s ago';
    if (delta.inMinutes < 60) return '${delta.inMinutes}m ago';
    if (delta.inHours < 24) return '${delta.inHours}h ago';
    return DateFormat('MMM d').format(ts.toLocal());
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.hourglass_empty, size: 48),
          const SizedBox(height: 12),
          Text('No signals yet',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(
            'Signals fire on each closed 15m candle once the backend has\n'
            'enough history (≈35 days). Come back later.',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
