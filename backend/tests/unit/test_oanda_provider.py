from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.services.market_data.oanda_provider import OandaProvider

BASE = "https://api-fxpractice.oanda.com"


@pytest.mark.asyncio
async def test_fetch_candles_maps_xauusd_and_parses_utc() -> None:
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/v3/instruments/XAU_USD/candles").mock(
            return_value=httpx.Response(
                200,
                json={
                    "instrument": "XAU_USD",
                    "granularity": "M15",
                    "candles": [
                        {
                            "complete": True,
                            "time": "2026-08-13T12:00:00.000000000Z",
                            "volume": 123,
                            "mid": {"o": "2400.10", "h": "2402.55", "l": "2399.80", "c": "2401.20"},
                        },
                        {
                            "complete": False,
                            "time": "2026-08-13T12:15:00.000000000Z",
                            "volume": 5,
                            "mid": {"o": "2401.20", "h": "2401.30", "l": "2401.10", "c": "2401.25"},
                        },
                    ],
                },
            )
        )

        provider = OandaProvider(api_token="test-token", api_url=BASE)
        try:
            candles = await provider.fetch_candles("XAUUSD", "15m", count=2)
        finally:
            await provider.aclose()

        assert route.called
        assert len(candles) == 1  # incomplete candle dropped
        c = candles[0]
        assert c.timestamp == datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
        assert c.timestamp.tzinfo is UTC
        assert c.open == 2400.10
        assert c.high == 2402.55
        assert c.low == 2399.80
        assert c.close == 2401.20
        assert c.volume == 123


@pytest.mark.asyncio
async def test_fetch_candles_rejects_unknown_symbol() -> None:
    provider = OandaProvider(api_token="test-token", api_url=BASE)
    try:
        with pytest.raises(ValueError, match="Unsupported symbol"):
            await provider.fetch_candles("BTCUSD", "15m", count=1)  # type: ignore[arg-type]
    finally:
        await provider.aclose()
