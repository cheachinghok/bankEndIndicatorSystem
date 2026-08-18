import 'package:flutter/material.dart';

import '../../features/market/data/market_repository.dart';

class TimeframeSelector extends StatelessWidget {
  const TimeframeSelector({
    super.key,
    required this.selected,
    required this.onSelected,
  });

  final Timeframe selected;
  final ValueChanged<Timeframe> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Row(
        children: [
          for (final tf in Timeframe.values)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: ChoiceChip(
                label: Text(tf.wire),
                selected: tf == selected,
                onSelected: (_) => onSelected(tf),
              ),
            ),
        ],
      ),
    );
  }
}
