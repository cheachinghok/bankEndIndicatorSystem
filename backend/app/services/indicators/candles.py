"""Extract OHLC series from a list of Candles.

Indicators take plain float lists so they're easy to test without needing
Candle fixtures; these helpers exist so callers don't repeat the comprehension.
"""
from collections.abc import Iterable

from app.services.market_data.models import Candle


def closes(candles: Iterable[Candle]) -> list[float]:
    return [c.close for c in candles]


def highs(candles: Iterable[Candle]) -> list[float]:
    return [c.high for c in candles]


def lows(candles: Iterable[Candle]) -> list[float]:
    return [c.low for c in candles]
