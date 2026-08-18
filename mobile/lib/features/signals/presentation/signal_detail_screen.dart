import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../shared/widgets/direction_badge.dart';
import '../domain/signal.dart';
import 'signal_providers.dart';

class SignalDetailScreen extends ConsumerWidget {
  const SignalDetailScreen({super.key, required this.signalId});
  final int signalId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(signalByIdProvider(signalId));
    return Scaffold(
      appBar: AppBar(title: const Text('Signal detail')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (s) => _Body(signal: s),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.signal});
  final Signal signal;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _headerCard(context),
        const SizedBox(height: 8),
        if (signal.isActionable) _tradeCard(context),
        if (signal.isActionable) const SizedBox(height: 8),
        _reasonsCard(context),
        if (signal.warnings.isNotEmpty) const SizedBox(height: 8),
        if (signal.warnings.isNotEmpty) _warningsCard(context),
        const SizedBox(height: 8),
        _breakdownCard(context),
        const SizedBox(height: 8),
        _disclaimerCard(context),
      ],
    );
  }

  Widget _headerCard(BuildContext context) {
    final tsFmt = DateFormat('MMM d · HH:mm').format(signal.generatedAt.toLocal());
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(signal.symbol,
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(width: 8),
                Text('· ${signal.timeframe}',
                    style: Theme.of(context).textTheme.bodyMedium),
                const Spacer(),
                DirectionBadge(direction: signal.directionEnum, large: true),
              ],
            ),
            const SizedBox(height: 20),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  signal.confidence.toStringAsFixed(0),
                  style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                    '/100',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            Text(
              'Setup Strength · not a probability of winning',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Text('Generated $tsFmt',
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }

  Widget _tradeCard(BuildContext context) {
    final priceFmt = NumberFormat('#,##0.00');
    Widget row(String label, double? value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              Text(label, style: Theme.of(context).textTheme.bodyMedium),
              const Spacer(),
              Text(
                value == null ? '—' : priceFmt.format(value),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
        );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Trade plan',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            row('Entry', signal.entry),
            row('Stop loss', signal.stopLoss),
            row('Take profit 1', signal.takeProfit1),
            row('Take profit 2', signal.takeProfit2),
            const Divider(height: 24),
            Row(
              children: [
                Text('Risk / Reward',
                    style: Theme.of(context).textTheme.bodyMedium),
                const Spacer(),
                Text(
                  signal.riskReward == null
                      ? '—'
                      : '1 : ${signal.riskReward!.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _reasonsCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Reasons',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            for (final reason in signal.reasons)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 3),
                      child: Icon(Icons.check_circle_outline,
                          size: 18, color: Colors.tealAccent),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(reason)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _warningsCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Warnings',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            for (final warning in signal.warnings)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 3),
                      child: Icon(Icons.warning_amber_rounded,
                          size: 18, color: Colors.amber),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(warning)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _breakdownCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Score breakdown',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            for (final entry in signal.breakdown.entries)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: Text(
                        entry.key,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    Expanded(
                      flex: 3,
                      child: Text(
                        entry.value.toStringAsFixed(2),
                        textAlign: TextAlign.right,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _disclaimerCard(BuildContext context) {
    return Card(
      color: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(
          'Not financial advice. Confidence is a "setup strength" score '
          'against the current strategy — it is not a probability of profit. '
          'Past performance never guarantees future results.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ),
    );
  }
}
