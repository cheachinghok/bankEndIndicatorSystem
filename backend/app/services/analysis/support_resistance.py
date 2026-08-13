"""Support/Resistance from recent swing clusters.

Approach: collect swing highs (resistance candidates) and swing lows (support
candidates) from the recent history, cluster levels that are within 0.5 ATR
of each other into single zones (so the same wick tested twice doesn't
double-count), then report the nearest one to current price.

Scoring (max 15) rewards being CLOSE to a favorable level:
    Near support (bullish setup)        8
    Support level tested multiple times +3
    Not near resistance                 +4
    (and mirror for bearish setups)
"""
import math
from collections.abc import Sequence

from app.services.analysis.structure import _find_swing_highs, _find_swing_lows
from app.services.analysis.types import (
    SUPPORT_RESISTANCE_MAX,
    Direction,
    SupportResistanceAnalysis,
)
from app.services.indicators.atr import atr_latest

MIN_HISTORY = 40
CLUSTER_ATR_UNITS = 0.5  # levels within 0.5*ATR of each other are one zone
NEAR_ATR_UNITS = 1.5     # "near" a level = within 1.5*ATR


def _cluster_levels(levels: list[float], tolerance: float) -> list[tuple[float, int]]:
    """Return list of (level, touch_count) sorted by level.

    Touch count is how many raw swings collapsed into that cluster — a level
    tested many times is stronger.
    """
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]
    for lv in sorted_levels[1:]:
        if lv - clusters[-1][-1] <= tolerance:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])
    return [(sum(c) / len(c), len(c)) for c in clusters]


def analyze_support_resistance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    direction_hint: Direction = Direction.NEUTRAL,
) -> SupportResistanceAnalysis:
    if len(closes) < MIN_HISTORY:
        return SupportResistanceAnalysis(
            score=0.0,
            nearest_support=None,
            nearest_resistance=None,
            distance_to_support_atr=None,
            distance_to_resistance_atr=None,
            reasons=[f"Not enough history for S/R (need ≥{MIN_HISTORY} candles)"],
        )

    atr = atr_latest(highs, lows, closes)
    if math.isnan(atr) or atr <= 0:
        return SupportResistanceAnalysis(
            score=0.0,
            nearest_support=None,
            nearest_resistance=None,
            distance_to_support_atr=None,
            distance_to_resistance_atr=None,
            reasons=["ATR unavailable — cannot compute S/R"],
        )

    price = closes[-1]
    tolerance = CLUSTER_ATR_UNITS * atr

    supports = _cluster_levels([v for _, v in _find_swing_lows(lows)], tolerance)
    resistances = _cluster_levels([v for _, v in _find_swing_highs(highs)], tolerance)

    supports_below = [(lv, n) for lv, n in supports if lv < price]
    resistances_above = [(lv, n) for lv, n in resistances if lv > price]

    nearest_support = max(supports_below, key=lambda t: t[0])[0] if supports_below else None
    nearest_resistance = min(resistances_above, key=lambda t: t[0])[0] if resistances_above else None
    support_touches = next((n for lv, n in supports_below if lv == nearest_support), 0) if nearest_support else 0
    resistance_touches = next((n for lv, n in resistances_above if lv == nearest_resistance), 0) if nearest_resistance else 0

    d_supp = (price - nearest_support) / atr if nearest_support is not None else None
    d_res = (nearest_resistance - price) / atr if nearest_resistance is not None else None

    reasons: list[str] = []
    score = 0.0

    if direction_hint == Direction.BULLISH:
        if d_supp is not None and d_supp <= NEAR_ATR_UNITS:
            score += 8
            reasons.append(f"Price near support {nearest_support:.2f} ({d_supp:.1f} ATR away)")
            if support_touches >= 2:
                score += 3
                reasons.append(f"Support tested {support_touches}× — strong zone")
        if d_res is None or d_res > NEAR_ATR_UNITS:
            score += 4
            reasons.append("No immediate resistance overhead")
        else:
            reasons.append(f"Resistance {nearest_resistance:.2f} only {d_res:.1f} ATR above — limited room")
    elif direction_hint == Direction.BEARISH:
        if d_res is not None and d_res <= NEAR_ATR_UNITS:
            score += 8
            reasons.append(f"Price near resistance {nearest_resistance:.2f} ({d_res:.1f} ATR away)")
            if resistance_touches >= 2:
                score += 3
                reasons.append(f"Resistance tested {resistance_touches}× — strong zone")
        if d_supp is None or d_supp > NEAR_ATR_UNITS:
            score += 4
            reasons.append("No immediate support below")
        else:
            reasons.append(f"Support {nearest_support:.2f} only {d_supp:.1f} ATR below — limited room")
    else:
        reasons.append("No trend direction — S/R proximity not scored")

    return SupportResistanceAnalysis(
        score=min(score, SUPPORT_RESISTANCE_MAX),
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        distance_to_support_atr=d_supp,
        distance_to_resistance_atr=d_res,
        reasons=reasons,
    )
