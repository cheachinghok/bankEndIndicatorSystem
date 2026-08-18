import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../features/signals/domain/signal.dart';

class DirectionBadge extends StatelessWidget {
  const DirectionBadge({
    super.key,
    required this.direction,
    this.large = false,
  });

  final SignalDirection direction;
  final bool large;

  Color _color() => switch (direction) {
        SignalDirection.buy => AppTheme.bullish(),
        SignalDirection.sell => AppTheme.bearish(),
        SignalDirection.wait => Colors.amber,
        SignalDirection.unknown => Colors.grey,
      };

  IconData _icon() => switch (direction) {
        SignalDirection.buy => Icons.trending_up,
        SignalDirection.sell => Icons.trending_down,
        SignalDirection.wait => Icons.pause_circle_outline,
        SignalDirection.unknown => Icons.help_outline,
      };

  @override
  Widget build(BuildContext context) {
    final color = _color();
    final padH = large ? 14.0 : 10.0;
    final padV = large ? 8.0 : 4.0;
    final iconSize = large ? 22.0 : 16.0;
    final textStyle = large
        ? Theme.of(context)
            .textTheme
            .titleLarge
            ?.copyWith(color: color, fontWeight: FontWeight.w700)
        : Theme.of(context)
            .textTheme
            .labelLarge
            ?.copyWith(color: color, fontWeight: FontWeight.w700);

    return Container(
      padding: EdgeInsets.symmetric(horizontal: padH, vertical: padV),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(large ? 10 : 6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon(), color: color, size: iconSize),
          const SizedBox(width: 6),
          Text(direction.label, style: textStyle),
        ],
      ),
    );
  }
}
