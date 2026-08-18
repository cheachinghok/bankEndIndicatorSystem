import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../features/market/domain/candle.dart';

/// Candlestick chart drawn with a CustomPainter — no external candle
/// library. Bodies use bull/bear colors; wicks are thin lines drawn to
/// the high/low.
class CandlestickChart extends StatelessWidget {
  const CandlestickChart({
    super.key,
    required this.candles,
    this.axisPadding = const EdgeInsets.only(top: 8, right: 48, bottom: 20, left: 8),
    this.maxCandles = 80,
  });

  final List<Candle> candles;
  final EdgeInsets axisPadding;
  final int maxCandles;

  @override
  Widget build(BuildContext context) {
    if (candles.isEmpty) {
      return const Center(child: Text('No data'));
    }
    final visible = candles.length > maxCandles
        ? candles.sublist(candles.length - maxCandles)
        : candles;
    return LayoutBuilder(
      builder: (context, constraints) {
        return CustomPaint(
          size: Size(constraints.maxWidth, constraints.maxHeight),
          painter: _CandlePainter(
            candles: visible,
            bull: AppTheme.bullish(),
            bear: AppTheme.bearish(),
            grid: Colors.white.withValues(alpha: 0.08),
            axisText: TextStyle(
              color: Colors.white.withValues(alpha: 0.55),
              fontSize: 10,
            ),
            padding: axisPadding,
          ),
        );
      },
    );
  }
}

class _CandlePainter extends CustomPainter {
  _CandlePainter({
    required this.candles,
    required this.bull,
    required this.bear,
    required this.grid,
    required this.axisText,
    required this.padding,
  });

  final List<Candle> candles;
  final Color bull;
  final Color bear;
  final Color grid;
  final TextStyle axisText;
  final EdgeInsets padding;

  @override
  void paint(Canvas canvas, Size size) {
    final chartRect = Rect.fromLTRB(
      padding.left,
      padding.top,
      size.width - padding.right,
      size.height - padding.bottom,
    );

    // Y range across visible candles.
    final lowestLow = candles.map((c) => c.low).reduce((a, b) => a < b ? a : b);
    final highestHigh = candles.map((c) => c.high).reduce((a, b) => a > b ? a : b);
    final rangePad = (highestHigh - lowestLow) * 0.08;
    final yMin = lowestLow - rangePad;
    final yMax = highestHigh + rangePad;

    double yFor(double price) {
      final t = (price - yMin) / (yMax - yMin);
      return chartRect.bottom - t * chartRect.height;
    }

    // Grid + labels on the right side.
    final gridPaint = Paint()..color = grid..strokeWidth = 1;
    const yTicks = 4;
    for (int i = 0; i <= yTicks; i++) {
      final price = yMin + (yMax - yMin) * (i / yTicks);
      final y = yFor(price);
      canvas.drawLine(Offset(chartRect.left, y), Offset(chartRect.right, y), gridPaint);
      final tp = TextPainter(
        text: TextSpan(text: price.toStringAsFixed(1), style: axisText),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(chartRect.right + 4, y - tp.height / 2));
    }

    // Candle sizing.
    final n = candles.length;
    final slot = chartRect.width / n;
    final bodyWidth = (slot * 0.7).clamp(1.0, 12.0);

    final bullFill = Paint()..color = bull;
    final bearFill = Paint()..color = bear;
    final bullStroke = Paint()..color = bull..strokeWidth = 1;
    final bearStroke = Paint()..color = bear..strokeWidth = 1;

    for (int i = 0; i < n; i++) {
      final c = candles[i];
      final centerX = chartRect.left + slot * (i + 0.5);
      final isBull = c.close >= c.open;
      final wickPaint = isBull ? bullStroke : bearStroke;
      canvas.drawLine(
        Offset(centerX, yFor(c.high)),
        Offset(centerX, yFor(c.low)),
        wickPaint,
      );
      final yOpen = yFor(c.open);
      final yClose = yFor(c.close);
      final rect = Rect.fromLTRB(
        centerX - bodyWidth / 2,
        yOpen < yClose ? yOpen : yClose,
        centerX + bodyWidth / 2,
        yOpen < yClose ? yClose : yOpen,
      );
      canvas.drawRect(rect.height < 1 ? rect.inflate(0.5) : rect,
          isBull ? bullFill : bearFill);
    }

    // First / last timestamp labels along the x axis.
    final firstText = TextPainter(
      text: TextSpan(text: _fmtTs(candles.first.timestamp), style: axisText),
      textDirection: TextDirection.ltr,
    )..layout();
    firstText.paint(canvas, Offset(chartRect.left, chartRect.bottom + 4));
    final lastText = TextPainter(
      text: TextSpan(text: _fmtTs(candles.last.timestamp), style: axisText),
      textDirection: TextDirection.ltr,
    )..layout();
    lastText.paint(
      canvas,
      Offset(chartRect.right - lastText.width, chartRect.bottom + 4),
    );
  }

  String _fmtTs(DateTime ts) {
    final local = ts.toLocal();
    // e.g. "Aug 14 14:30"
    const months = [
      'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec',
    ];
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '${months[local.month - 1]} ${local.day} $hh:$mm';
  }

  @override
  bool shouldRepaint(covariant _CandlePainter old) =>
      old.candles != candles || old.bull != bull || old.bear != bear;
}
