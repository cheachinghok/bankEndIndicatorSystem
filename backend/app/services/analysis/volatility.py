"""Volatility analysis: ATR14 as % of price.

Buckets are gold-specific — XAUUSD typically runs 0.2%–0.6% ATR on 15m/1h.

    LOW      < 0.15%       score 6
    NORMAL   0.15%–0.60%   score 10   (sweet spot for trend-following)
    HIGH     0.60%–1.20%   score 5    (still tradeable, wider stops)
    EXTREME  > 1.20%       score 2    (WAIT recommended — news / thin book)

Volatility has no `direction` — it modulates confidence for both bull and bear.
"""
import math
from collections.abc import Sequence

from app.services.analysis.types import VOLATILITY_MAX, VolatilityAnalysis
from app.services.indicators.atr import atr_latest

MIN_HISTORY = 20


def analyze_volatility(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> VolatilityAnalysis:
    if len(closes) < MIN_HISTORY:
        return VolatilityAnalysis(
            score=0.0,
            atr=math.nan,
            atr_pct=math.nan,
            level="UNKNOWN",
            reasons=[f"Not enough history for volatility (need ≥{MIN_HISTORY} candles)"],
        )

    atr = atr_latest(highs, lows, closes)
    price = closes[-1]
    atr_pct = (atr / price) * 100.0 if price > 0 else math.nan

    if math.isnan(atr_pct):
        return VolatilityAnalysis(score=0.0, atr=atr, atr_pct=atr_pct, level="UNKNOWN")

    if atr_pct < 0.15:
        level, score = "LOW", 6.0
        reason = f"Low volatility (ATR {atr_pct:.2f}% of price) — narrow ranges"
    elif atr_pct < 0.60:
        level, score = "NORMAL", VOLATILITY_MAX
        reason = f"Normal volatility (ATR {atr_pct:.2f}%)"
    elif atr_pct < 1.20:
        level, score = "HIGH", 5.0
        reason = f"High volatility (ATR {atr_pct:.2f}%) — use wider stops"
    else:
        level, score = "EXTREME", 2.0
        reason = f"Extreme volatility (ATR {atr_pct:.2f}%) — consider waiting"

    return VolatilityAnalysis(
        score=score, atr=atr, atr_pct=atr_pct, level=level, reasons=[reason]
    )
