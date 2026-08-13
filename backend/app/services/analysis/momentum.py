"""Momentum analysis: RSI + MACD.

Direction is determined by RSI (>50 bull / <50 bear) and MACD **line** sign
(fast EMA > slow EMA is bullish, and vice versa). The MACD histogram is
used separately as an acceleration bonus — histogram > 0 means the MACD
line is above its signal line, i.e. momentum is accelerating in the trend
direction. Critically, in a pure linear trend the histogram converges to
zero even though the trend is unambiguous, so we do NOT gate direction on
the histogram.

Scoring (max 20):
    RSI + MACD line agree on direction   8
    RSI in favorable zone                4
    Histogram agrees (acceleration)      4
    Not overbought/oversold vs trend     4
"""
import math
from collections.abc import Sequence

from app.services.analysis.types import MOMENTUM_MAX, Direction, MomentumAnalysis
from app.services.indicators.macd import macd_latest
from app.services.indicators.rsi import rsi_latest

MIN_HISTORY = 40  # enough to seed MACD(26) and RSI(14)
OVERBOUGHT = 70.0
OVERSOLD = 30.0


def analyze_momentum(closes: Sequence[float]) -> MomentumAnalysis:
    if len(closes) < MIN_HISTORY:
        return MomentumAnalysis(
            direction=Direction.NEUTRAL,
            score=0.0,
            rsi=math.nan,
            macd=math.nan,
            macd_signal=math.nan,
            macd_histogram=math.nan,
            reasons=[f"Not enough history for momentum (need ≥{MIN_HISTORY} closes)"],
        )

    rsi = rsi_latest(closes)
    macd, signal, hist = macd_latest(closes)

    reasons: list[str] = []
    rsi_bull = rsi > 50
    rsi_bear = rsi < 50
    macd_bull = macd > 0  # fast EMA > slow EMA
    macd_bear = macd < 0

    direction = Direction.NEUTRAL
    score = 0.0

    if rsi_bull and macd_bull:
        direction = Direction.BULLISH
        score += 8
        reasons.append(f"RSI {rsi:.1f} bullish and MACD line positive")
    elif rsi_bear and macd_bear:
        direction = Direction.BEARISH
        score += 8
        reasons.append(f"RSI {rsi:.1f} bearish and MACD line negative")
    else:
        reasons.append(f"RSI {rsi:.1f} vs MACD {macd:+.3f} disagree")

    # Additional points for confirming details.
    if direction == Direction.BULLISH:
        score += 4  # RSI already confirmed above
        if hist > 0:
            score += 4
            reasons.append("MACD histogram positive — bullish momentum accelerating")
        if rsi < OVERBOUGHT:
            score += 4
            reasons.append(f"RSI {rsi:.1f} not overbought")
        else:
            reasons.append(f"RSI {rsi:.1f} overbought — momentum may be exhausted")
    elif direction == Direction.BEARISH:
        score += 4
        if hist < 0:
            score += 4
            reasons.append("MACD histogram negative — bearish momentum accelerating")
        if rsi > OVERSOLD:
            score += 4
            reasons.append(f"RSI {rsi:.1f} not oversold")
        else:
            reasons.append(f"RSI {rsi:.1f} oversold — momentum may be exhausted")

    return MomentumAnalysis(
        direction=direction,
        score=min(score, MOMENTUM_MAX),
        rsi=rsi,
        macd=macd,
        macd_signal=signal,
        macd_histogram=hist,
        reasons=reasons,
    )
