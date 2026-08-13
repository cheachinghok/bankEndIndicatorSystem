"""Market structure analysis.

Swings are detected via a 5-bar fractal pattern:
    High(t) is a swing high if H(t-2), H(t-1) < H(t) > H(t+1), H(t+2)
    Low(t) is a swing low  if L(t-2), L(t-1) > L(t) < L(t+1), L(t+2)

Bullish structure:  higher-highs AND higher-lows (HH + HL)
Bearish structure:  lower-highs  AND lower-lows  (LH + LL)

BOS (Break of Structure): latest close breaks the most recent swing high
(bullish) or swing low (bearish) — continuation signal.

CHoCH (Change of Character): break in the opposite direction of the prior
trend — reversal signal, treated as noise for score purposes but flagged.

Scoring (max 20):
    HH+HL / LH+LL sequence      12
    BOS in trend direction       5
    3+ confirming swings         3
"""
from collections.abc import Sequence

from app.services.analysis.types import STRUCTURE_MAX, Direction, StructureAnalysis

MIN_HISTORY = 30
FRACTAL_HALF = 2  # 2 bars each side → 5-bar fractal
LOOKBACK_SWINGS = 4  # number of most recent swings we consider


def _find_swing_highs(highs: Sequence[float]) -> list[tuple[int, float]]:
    swings: list[tuple[int, float]] = []
    for i in range(FRACTAL_HALF, len(highs) - FRACTAL_HALF):
        h = highs[i]
        if all(highs[i - k] < h for k in range(1, FRACTAL_HALF + 1)) and all(
            highs[i + k] < h for k in range(1, FRACTAL_HALF + 1)
        ):
            swings.append((i, h))
    return swings


def _find_swing_lows(lows: Sequence[float]) -> list[tuple[int, float]]:
    swings: list[tuple[int, float]] = []
    for i in range(FRACTAL_HALF, len(lows) - FRACTAL_HALF):
        low = lows[i]
        if all(lows[i - k] > low for k in range(1, FRACTAL_HALF + 1)) and all(
            lows[i + k] > low for k in range(1, FRACTAL_HALF + 1)
        ):
            swings.append((i, low))
    return swings


def _monotonic(values: Sequence[float], ascending: bool) -> bool:
    if len(values) < 2:
        return False
    return all(
        (values[i] > values[i - 1]) if ascending else (values[i] < values[i - 1])
        for i in range(1, len(values))
    )


def analyze_structure(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> StructureAnalysis:
    if len(closes) < MIN_HISTORY:
        return StructureAnalysis(
            direction=Direction.NEUTRAL,
            score=0.0,
            swing_highs=[],
            swing_lows=[],
            bos=False,
            choch=False,
            reasons=[f"Not enough history for structure (need ≥{MIN_HISTORY} candles)"],
        )

    sh = _find_swing_highs(highs)[-LOOKBACK_SWINGS:]
    sl = _find_swing_lows(lows)[-LOOKBACK_SWINGS:]
    sh_values = [v for _, v in sh]
    sl_values = [v for _, v in sl]

    reasons: list[str] = []
    direction = Direction.NEUTRAL
    score = 0.0
    bos = False
    choch = False

    hh = _monotonic(sh_values, ascending=True)
    hl = _monotonic(sl_values, ascending=True)
    lh = _monotonic(sh_values, ascending=False)
    ll = _monotonic(sl_values, ascending=False)

    last_close = closes[-1]

    if hh and hl:
        direction = Direction.BULLISH
        score += 12
        reasons.append(f"Higher highs + higher lows (last {len(sh_values)} swings each)")
        if sh_values and last_close > sh_values[-1]:
            bos = True
            score += 5
            reasons.append("BOS: price broke last swing high")
        if len(sh_values) >= 3 and len(sl_values) >= 3:
            score += 3
    elif lh and ll:
        direction = Direction.BEARISH
        score += 12
        reasons.append(f"Lower highs + lower lows (last {len(sh_values)} swings each)")
        if sl_values and last_close < sl_values[-1]:
            bos = True
            score += 5
            reasons.append("BOS: price broke last swing low")
        if len(sh_values) >= 3 and len(sl_values) >= 3:
            score += 3
    else:
        # Check for CHoCH — a break against a prior trend segment.
        if sh_values and last_close > max(sh_values):
            choch = True
            reasons.append("CHoCH: price broke above all recent swing highs")
        elif sl_values and last_close < min(sl_values):
            choch = True
            reasons.append("CHoCH: price broke below all recent swing lows")
        else:
            reasons.append("No clear swing structure")

    return StructureAnalysis(
        direction=direction,
        score=min(score, STRUCTURE_MAX),
        swing_highs=sh_values,
        swing_lows=sl_values,
        bos=bos,
        choch=choch,
        reasons=reasons,
    )
