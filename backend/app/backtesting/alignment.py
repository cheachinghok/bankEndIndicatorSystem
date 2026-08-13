"""Multi-timeframe candle alignment.

At any wall-clock instant t, only candles whose CLOSE time is <= t are
"known" — including any others would be look-ahead. This module owns that
invariant.

Convention: `Candle.timestamp` is the OPEN time (matches OANDA). Close time
= open + duration(tf).
"""
from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.services.market_data.models import Candle, Timeframe

_DURATION: dict[Timeframe, timedelta] = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


def timeframe_duration(tf: Timeframe) -> timedelta:
    return _DURATION[tf]


def visible_candles(
    candles: Sequence[Candle],
    timeframe: Timeframe,
    at_instant: datetime,
) -> list[Candle]:
    """Return the sub-list of `candles` whose close time is <= at_instant.

    `candles` must be sorted ascending by timestamp. Uses bisect for O(log n).
    """
    duration = _DURATION[timeframe]
    # A candle at open=T closes at T + duration. It's visible at instant `at`
    # when T + duration <= at, i.e. T <= at - duration.
    threshold = at_instant - duration
    # bisect_right on timestamps finds the count of candles with timestamp <= threshold
    # when we key by the open time. Build a lightweight key view.
    n = len(candles)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if candles[mid].timestamp <= threshold:
            lo = mid + 1
        else:
            hi = mid
    return list(candles[:lo])


def align_all_timeframes(
    candles_by_tf: dict[Timeframe, Sequence[Candle]],
    at_instant: datetime,
) -> dict[Timeframe, list[Candle]]:
    """Convenience wrapper — apply visible_candles across every TF."""
    return {
        tf: visible_candles(candles, tf, at_instant)
        for tf, candles in candles_by_tf.items()
    }
