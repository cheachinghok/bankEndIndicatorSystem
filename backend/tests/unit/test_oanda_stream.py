from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.services.market_data.oanda_provider import OandaProvider, _price_message_to_tick

STREAM_BASE = "https://stream-fxpractice.oanda.com"


def test_price_message_to_tick_parses_ok() -> None:
    msg = {
        "type": "PRICE",
        "instrument": "XAU_USD",
        "time": "2026-08-13T12:00:00.123456789Z",
        "bids": [{"price": "2400.10"}],
        "asks": [{"price": "2400.30"}],
        "tradeable": True,
    }
    tick = _price_message_to_tick(msg)
    assert tick is not None
    assert tick.symbol == "XAUUSD"
    assert tick.bid == 2400.10
    assert tick.ask == 2400.30
    assert tick.mid == 2400.20
    assert tick.tradeable is True
    assert tick.timestamp.tzinfo is UTC


def test_price_message_returns_none_on_bad_shape() -> None:
    assert _price_message_to_tick({"type": "PRICE"}) is None
    assert _price_message_to_tick({"instrument": "XAU_USD", "bids": [], "asks": []}) is None


@pytest.mark.asyncio
async def test_stream_prices_yields_ticks_and_skips_heartbeats() -> None:
    body = (
        # Heartbeat — must be skipped.
        b'{"type":"HEARTBEAT","time":"2026-08-13T12:00:00Z"}\n'
        # Real price.
        b'{"type":"PRICE","instrument":"XAU_USD","time":"2026-08-13T12:00:01Z",'
        b'"bids":[{"price":"2400.10"}],"asks":[{"price":"2400.30"}],"tradeable":true}\n'
        # Malformed JSON — must be skipped.
        b'not-json-line\n'
        # Second price.
        b'{"type":"PRICE","instrument":"XAU_USD","time":"2026-08-13T12:00:02Z",'
        b'"bids":[{"price":"2400.15"}],"asks":[{"price":"2400.35"}],"tradeable":true}\n'
    )
    with respx.mock(base_url=STREAM_BASE) as mock:
        mock.get("/v3/accounts/acc-1/pricing/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        provider = OandaProvider(
            api_token="test-token",
            api_url="https://api-fxpractice.oanda.com",
            stream_url=STREAM_BASE,
            account_id="acc-1",
        )
        try:
            ticks = [t async for t in provider.stream_prices(["XAUUSD"])]
        finally:
            await provider.aclose()

        assert len(ticks) == 2
        assert ticks[0].mid == 2400.20
        assert ticks[1].mid == 2400.25
        assert ticks[0].timestamp == datetime(2026, 8, 13, 12, 0, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_stream_requires_account_id() -> None:
    provider = OandaProvider(
        api_token="test-token",
        api_url="https://api-fxpractice.oanda.com",
        stream_url=STREAM_BASE,
        account_id="",
    )
    try:
        with pytest.raises(RuntimeError, match="account_id"):
            async for _ in provider.stream_prices(["XAUUSD"]):
                pass
    finally:
        await provider.aclose()
