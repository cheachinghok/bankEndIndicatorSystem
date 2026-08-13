from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Timeframe = Literal["5m", "15m", "30m", "1h", "4h", "1d"]

TIMEFRAMES: tuple[Timeframe, ...] = ("5m", "15m", "30m", "1h", "4h", "1d")


@dataclass(frozen=True, slots=True)
class Candle:
    """OHLC candle. `timestamp` is always UTC-aware."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Candle.timestamp must be timezone-aware (UTC)")


@dataclass(frozen=True, slots=True)
class PriceTick:
    """A single live mid-price observation. `timestamp` is UTC-aware."""

    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    tradeable: bool = True

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
