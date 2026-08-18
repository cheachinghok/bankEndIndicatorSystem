"""Trend analysis via EMA stacking.

Direction rules (loosened in Phase 8.6 to fire signals more often on real
markets where strict stacking is rare):

    Count of 3 bullish conditions:
        price > EMA200
        EMA20  > EMA50
        EMA50  > EMA200
    3 hits → strong BULLISH (full stack score)
    2 hits → weak BULLISH
    Same, mirrored, for BEARISH.
    <2 hits either way → NEUTRAL.

Scoring (max 25):
    Full stack (3/3)         15
    Partial (2/3)             8
    Price on trend side       5   (extra beyond the above if 3/3)
    EMA20 slope in direction  3
    Base bonus (3/3 only)     2
"""
import math
from collections.abc import Sequence

from app.services.analysis.types import TREND_MAX, Direction, TrendAnalysis
from app.services.indicators.ema import ema, ema_latest

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

    # Range detection: if the three EMAs are all within 0.1% of each other,
    # the market is flat/ranging — skip direction detection so we don't
    # pick a side from floating-point drift.
    ema_span = max(ema20, ema50, ema200) - min(ema20, ema50, ema200)
    if ema_span / max(ema200, 1e-9) < 0.001:
        return TrendAnalysis(
            direction=Direction.NEUTRAL,
            score=0.0,
            ema20=ema20,
            ema50=ema50,
            ema200=ema200,
            price=price,
            reasons=["EMAs bunched (<0.1% spread) — market is ranging"],
        )

    bull_votes = sum([price > ema200, ema20 > ema50, ema50 > ema200])
    bear_votes = sum([price < ema200, ema20 < ema50, ema50 < ema200])

    reasons: list[str] = []
    direction = Direction.NEUTRAL
    score = 0.0

    if bull_votes == 3:
        direction = Direction.BULLISH
        score = 15 + 5 + 2  # base + price bonus (implicit in vote) + full-stack bonus
        reasons.append("Full bullish stack: price > EMA20 > EMA50 > EMA200")
        if ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope up")
    elif bear_votes == 3:
        direction = Direction.BEARISH
        score = 15 + 5 + 2
        reasons.append("Full bearish stack: price < EMA20 < EMA50 < EMA200")
        if not ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope down")
    elif bull_votes == 2:
        direction = Direction.BULLISH
        score = 8
        reasons.append(f"Partial bullish alignment ({bull_votes}/3 conditions)")
        if ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope up")
    elif bear_votes == 2:
        direction = Direction.BEARISH
        score = 8
        reasons.append(f"Partial bearish alignment ({bear_votes}/3 conditions)")
        if not ema20_slope_up:
            score += 3
            reasons.append("EMA20 slope down")
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
