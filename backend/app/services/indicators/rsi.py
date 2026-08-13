"""Relative Strength Index — Wilder's smoothing.

Convention: values[0..length-1] are NaN (need `length` gains/losses to seed).
The value at index `length` uses SMA of the first `length` gains and losses;
subsequent values use Wilder's smoothing (alpha = 1/length).

This matches TradingView's default RSI (which uses Wilder), not the
"exponential RSI" variant.
"""
import math
from collections.abc import Sequence


def rsi(values: Sequence[float], length: int = 14) -> list[float]:
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")

    n = len(values)
    result: list[float] = [math.nan] * n
    if n <= length:
        return result

    gains: list[float] = [0.0] * n
    losses: list[float] = [0.0] * n
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        gains[i] = max(delta, 0.0)
        losses[i] = max(-delta, 0.0)

    # Seed at index `length`: SMA of the first `length` gains/losses (indices 1..length).
    avg_gain = sum(gains[1 : length + 1]) / length
    avg_loss = sum(losses[1 : length + 1]) / length
    result[length] = _rsi_from(avg_gain, avg_loss)

    # Wilder smoothing for the rest.
    for i in range(length + 1, n):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        result[i] = _rsi_from(avg_gain, avg_loss)
    return result


def rsi_latest(values: Sequence[float], length: int = 14) -> float:
    series = rsi(values, length)
    return series[-1] if series else math.nan


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0  # flat market → 50 by convention
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
