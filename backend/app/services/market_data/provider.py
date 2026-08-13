from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from app.services.market_data.models import Candle, PriceTick, Timeframe


class MarketDataProvider(ABC):
    """Abstract source of market data.

    Implementations must return UTC-aware timestamps and normalize symbols to
    the platform-wide code (e.g. XAUUSD) regardless of the provider's native code.
    """

    @abstractmethod
    async def fetch_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        count: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[Candle]:
        ...


class StreamingMarketDataProvider(MarketDataProvider):
    """A provider that also supports live price streaming.

    Implementations yield PriceTick objects until the caller cancels the iterator.
    Reconnect / backoff is the caller's responsibility (kept out of the provider
    to keep the interface simple and easy to fake in tests).
    """

    @abstractmethod
    def stream_prices(self, symbols: list[str]) -> AsyncIterator[PriceTick]:
        ...
