"""Average True Range — Wilder's smoothing.

    TR(t) = max(High(t)-Low(t), |High(t)-Close(t-1)|, |Low(t)-Close(t-1)|)
    ATR(t) = Wilder-smoothed TR with alpha = 1/length

Convention: values[0..length-1] are NaN (need `length` TR values to seed).
"""
import math
from collections.abc import Sequence


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    length: int = 14,
) -> list[float]:
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs/lows/closes must be same length")

    n = len(highs)
    result: list[float] = [math.nan] * n
    if n < length + 1:
        return result

    # True Range series (TR[0] is NaN — no previous close).
    tr: list[float] = [math.nan] * n
    for i in range(1, n):
        prev_close = closes[i - 1]
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )

    # Seed at index `length`: SMA of TR[1..length].
    seed = sum(tr[1 : length + 1]) / length
    result[length] = seed
    prev = seed

    # Wilder smoothing: ATR(t) = (ATR(t-1)*(length-1) + TR(t)) / length
    for i in range(length + 1, n):
        prev = (prev * (length - 1) + tr[i]) / length
        result[i] = prev
    return result


def atr_latest(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    length: int = 14,
) -> float:
    series = atr(highs, lows, closes, length)
    return series[-1] if series else math.nan
