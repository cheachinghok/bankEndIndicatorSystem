"""MACD — Moving Average Convergence/Divergence.

    macd_line = EMA(closes, fast) - EMA(closes, slow)
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line

Defaults 12/26/9 match Appel's original (and TradingView).
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.indicators.ema import ema


@dataclass(frozen=True, slots=True)
class MacdResult:
    macd: list[float]
    signal: list[float]
    histogram: list[float]


def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MacdResult:
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be < slow ({slow})")

    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line: list[float] = [
        f - s if not (math.isnan(f) or math.isnan(s)) else math.nan
        for f, s in zip(ema_fast, ema_slow)
    ]

    # EMA of macd_line — feed only the non-NaN tail so the signal EMA seeds
    # correctly, then pad NaN back on the left.
    tail_start = next(
        (i for i, v in enumerate(macd_line) if not math.isnan(v)),
        len(macd_line),
    )
    tail = macd_line[tail_start:]
    signal_tail = ema(tail, signal)
    signal_line: list[float] = [math.nan] * tail_start + signal_tail

    histogram: list[float] = [
        m - s if not (math.isnan(m) or math.isnan(s)) else math.nan
        for m, s in zip(macd_line, signal_line)
    ]
    return MacdResult(macd=macd_line, signal=signal_line, histogram=histogram)


def macd_latest(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float, float, float]:
    r = macd(values, fast, slow, signal)
    return r.macd[-1], r.signal[-1], r.histogram[-1]
