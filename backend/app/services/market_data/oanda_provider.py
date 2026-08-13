import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from app.services.market_data.models import Candle, PriceTick, Timeframe
from app.services.market_data.provider import StreamingMarketDataProvider

_SYMBOL_MAP: dict[str, str] = {
    "XAUUSD": "XAU_USD",
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDJPY": "USD_JPY",
}

_GRANULARITY_MAP: dict[Timeframe, str] = {
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
}


_REVERSE_SYMBOL_MAP: dict[str, str] = {v: k for k, v in _SYMBOL_MAP.items()}


def _to_provider_symbol(symbol: str) -> str:
    try:
        return _SYMBOL_MAP[symbol.upper()]
    except KeyError as e:
        raise ValueError(f"Unsupported symbol: {symbol}") from e


def _from_provider_symbol(instrument: str) -> str:
    try:
        return _REVERSE_SYMBOL_MAP[instrument]
    except KeyError as e:
        raise ValueError(f"Unknown OANDA instrument: {instrument}") from e


class OandaProvider(StreamingMarketDataProvider):
    """OANDA v20 REST + streaming market-data provider.

    REST docs:   https://developer.oanda.com/rest-live-v20/instrument-ep/
    Stream docs: https://developer.oanda.com/rest-live-v20/pricing-ep/

    The pricing stream is JSON-Lines (one JSON object per line), not SSE.
    Each PRICE line becomes a PriceTick. HEARTBEAT lines are dropped by the
    provider — the caller enforces the heartbeat watchdog since only it knows
    what "too long without a heartbeat" means for its use case.
    """

    def __init__(
        self,
        api_token: str,
        api_url: str = "https://api-fxpractice.oanda.com",
        stream_url: str | None = None,
        account_id: str = "",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        # OANDA has separate host for streaming.
        self._stream_url = (stream_url or api_url.replace("api-", "stream-")).rstrip("/")
        self._account_id = account_id
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept-Datetime-Format": "RFC3339",
        }
        self._client = client
        self._timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout, headers=self._headers)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def stream_prices(self, symbols: list[str]) -> AsyncIterator[PriceTick]:
        if not self._account_id:
            raise RuntimeError("OANDA account_id is required for streaming.")
        instruments = ",".join(_to_provider_symbol(s) for s in symbols)
        url = f"{self._stream_url}/v3/accounts/{self._account_id}/pricing/stream"
        params = {"instruments": instruments}

        # Use a fresh client with no read timeout — the stream is intentionally long-lived.
        stream_timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
        async with httpx.AsyncClient(headers=self._headers, timeout=stream_timeout) as client:
            async with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                # NOTE: we consume raw bytes and split on newlines ourselves.
                # httpx.aiter_lines() buffers indefinitely on
                # `content-type: application/octet-stream` (OANDA's stream MIME),
                # so lines were never yielded until the stream closed.
                buffer = b""
                async for chunk in response.aiter_bytes():
                    buffer += chunk
                    while b"\n" in buffer:
                        raw_line, buffer = buffer.split(b"\n", 1)
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if obj.get("type") != "PRICE":
                            # HEARTBEAT and other message types are silently dropped.
                            continue
                        tick = _price_message_to_tick(obj)
                        if tick is not None:
                            yield tick

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        count: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[Candle]:
        instrument = _to_provider_symbol(symbol)
        granularity = _GRANULARITY_MAP[timeframe]

        params: dict[str, str | int] = {
            "granularity": granularity,
            "price": "M",  # midpoint prices
        }
        if count is not None:
            params["count"] = count
        if from_time is not None:
            params["from"] = from_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if to_time is not None:
            params["to"] = to_time.astimezone(UTC).isoformat().replace("+00:00", "Z")

        url = f"{self._api_url}/v3/instruments/{instrument}/candles"
        client = self._get_client()
        response = await client.get(url, params=params, headers=self._headers)
        response.raise_for_status()
        payload = response.json()

        candles: list[Candle] = []
        for raw in payload.get("candles", []):
            if not raw.get("complete", False):
                continue  # skip in-flight candles — closed candles only
            mid = raw["mid"]
            candles.append(
                Candle(
                    timestamp=_parse_rfc3339(raw["time"]),
                    open=float(mid["o"]),
                    high=float(mid["h"]),
                    low=float(mid["l"]),
                    close=float(mid["c"]),
                    volume=float(raw.get("volume", 0)),
                )
            )
        return candles


def _price_message_to_tick(obj: dict) -> PriceTick | None:
    """Convert an OANDA PRICE JSON message to a PriceTick.

    OANDA PRICE shape (simplified):
      {"type": "PRICE", "instrument": "XAU_USD", "time": "2026-...",
       "bids": [{"price": "2401.05"}, ...],
       "asks": [{"price": "2401.35"}, ...],
       "tradeable": true}
    """
    try:
        instrument = obj["instrument"]
        symbol = _from_provider_symbol(instrument)
        bids = obj["bids"]
        asks = obj["asks"]
        if not bids or not asks:
            return None
        return PriceTick(
            symbol=symbol,
            timestamp=_parse_rfc3339(obj["time"]),
            bid=float(bids[0]["price"]),
            ask=float(asks[0]["price"]),
            tradeable=bool(obj.get("tradeable", True)),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _parse_rfc3339(value: str) -> datetime:
    # OANDA returns e.g. "2026-08-13T12:00:00.000000000Z"; datetime.fromisoformat
    # in Python 3.12 accepts trailing Z but not nanosecond precision.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    # Truncate fractional seconds to microseconds.
    if "." in value:
        head, tail = value.split(".", 1)
        frac, _, tz = tail.partition("+")
        frac = frac[:6]
        value = f"{head}.{frac}+{tz}" if tz else f"{head}.{frac}"
    return datetime.fromisoformat(value)
