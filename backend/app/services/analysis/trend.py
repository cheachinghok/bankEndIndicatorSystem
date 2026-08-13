"""Trend analysis via EMA stacking.

Bullish stack:  price > EMA20 > EMA50 > EMA200
Bearish stack:  price < EMA20 < EMA50 < EMA200

Scoring (max 25):
    Full alignment           15
    Price on trend side       5
    EMA20 slope in direction  3
    Not equal to zero         2
"""
import math
from collections.abc import Sequence

from app.services.analysis.types import TREND_MAX, Direction, TrendAnalysis
from app.services.indicators.ema import ema_latest, ema

MIN_HISTORY = 210  # need at least EMA200 seed + a few extra for slope check


def analyze_trend(closes: Sequence[float]) -> TrendAnalysis:
    if len(closes) < MIN_HISTORY:
        return TrendAnalysis(
            direction=Direction.NEUTRAL,
            score=0.0,
            ema20=math.nan,
            ema50=math.nan,
            ema200=math.nan,
            price=closes[-1] if closes else math.nan,
            reasons=[f"Not enough history for trend (need ≥{MIN_HISTORY} closes)"],
        )

    price = closes[-1]
    ema20 = ema_latest(closes, 20)
    ema50 = ema_latest(closes, 50)
    ema200 = ema_latest(closes, 200)
    ema20_series = ema(closes, 20)
    ema20_slope_up = ema20_series[-1] > ema20_series[-3]  # 3-bar slope

    reasons: list[str] = []
    direction = Direction.NEUTRAL
    score = 0.0

    bullish_stack = ema20 > ema50 > ema200
    bearish_stack = ema20 < ema50 < ema200

    if bullish_stack:
        direction = Direction.BULLISH
        score += 15
        reasons.append("EMA20 > EMA50 > EMA200 (bullish stack)")
        if price > ema200:
            score += 5
            reasons.append("Price above EMA200")
        if ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope up")
        score += 2  # base bonus for having a clear stack
    elif bearish_stack:
        direction = Direction.BEARISH
        score += 15
        reasons.append("EMA20 < EMA50 < EMA200 (bearish stack)")
        if price < ema200:
            score += 5
            reasons.append("Price below EMA200")
        if not ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope down")
        score += 2
    else:
        # Partial alignment: award small score if price on same side of EMA200 as EMA20.
        if price > ema200 and ema20 > ema50:
            direction = Direction.BULLISH
            score = 8
            reasons.append("Partial bullish alignment (EMA20>EMA50, price>EMA200)")
        elif price < ema200 and ema20 < ema50:
            direction = Direction.BEARISH
            score = 8
            reasons.append("Partial bearish alignment (EMA20<EMA50, price<EMA200)")
        else:
            reasons.append("EMAs not aligned — no clear trend")

    return TrendAnalysis(
        direction=direction,
        score=min(score, TREND_MAX),
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        price=price,
        reasons=reasons,
    )
