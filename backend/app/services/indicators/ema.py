"""Exponential Moving Average.

Convention: the first (length-1) values of the returned series are NaN. The
value at index `length-1` is the SMA of the first `length` inputs (the seed);
subsequent values follow the standard EMA recursion with alpha = 2/(length+1).

This "SMA-seeded EMA" is what most trading platforms (TradingView, MT5) use.
"""
import math
from collections.abc import Sequence


def ema(values: Sequence[float], length: int) -> list[float]:
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")

    n = len(values)
    result: list[float] = [math.nan] * n
    if n < length:
        return result

    alpha = 2.0 / (length + 1)
    seed = sum(values[:length]) / length
    result[length - 1] = seed
    prev = seed
    for i in range(length, n):
        prev = alpha * values[i] + (1 - alpha) * prev
        result[i] = prev
    return result


def ema_latest(values: Sequence[float], length: int) -> float:
    """The most recent EMA value, or NaN if there aren't enough inputs."""
    series = ema(values, length)
    return series[-1] if series else math.nan


class IncrementalEMA:
    """EMA that updates in O(1) per new value.

    Useful for the live signal path where a new closed candle arrives and we
    want to update EMAs without recomputing over the whole history.

    Seed with either the last known EMA value (from a batch warmup) or an
    initial series of at least `length` values. Once seeded, call push()
    with each new close.
    """

    def __init__(self, length: int, *, seed: float | None = None) -> None:
        if length <= 0:
            raise ValueError(f"length must be positive, got {length}")
        self._length = length
        self._alpha = 2.0 / (length + 1)
        self._value: float | None = seed

    @classmethod
    def from_series(cls, values: Sequence[float], length: int) -> "IncrementalEMA":
        latest = ema_latest(values, length)
        return cls(length, seed=None if math.isnan(latest) else latest)

    def push(self, value: float) -> float:
        if self._value is None:
            self._value = value
            return value
        self._value = self._alpha * value + (1 - self._alpha) * self._value
        return self._value

    @property
    def value(self) -> float | None:
        return self._value

    @property
    def length(self) -> int:
        return self._length
