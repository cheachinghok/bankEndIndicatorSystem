"""Unit test for the price stream worker: verify a tick is stored in Redis
(latest-price key) AND published on the prices channel."""
import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis

from app.core.redis import latest_price_key, prices_channel
from app.services.market_data.models import PriceTick
from app.services.market_data.provider import StreamingMarketDataProvider
from app.workers.price_stream import _publish_tick


class _FakeProvider(StreamingMarketDataProvider):
    def __init__(self, ticks: list[PriceTick]) -> None:
        self._ticks = ticks

    async def fetch_candles(self, *args, **kwargs):  # pragma: no cover
        return []

    async def stream_prices(self, symbols: list[str]) -> AsyncIterator[PriceTick]:
        for t in self._ticks:
            yield t


@pytest.mark.asyncio
async def test_publish_tick_writes_key_and_publishes() -> None:
    """Uses a real local Redis (from docker-compose) — skip if unavailable."""
    from app.core.config import get_settings

    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception:
        pytest.skip("Redis not reachable — skipping integration slice of unit test")

    tick = PriceTick(
        symbol="XAUUSD",
        timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
        bid=2400.1,
        ask=2400.3,
    )

    pubsub = redis.pubsub()
    await pubsub.subscribe(prices_channel("XAUUSD"))
    # Discard the subscribe confirmation.
    await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), 2.0)

    await _publish_tick(redis, tick)

    stored = await redis.get(latest_price_key("XAUUSD"))
    assert stored is not None
    stored_obj = json.loads(stored)
    assert stored_obj["bid"] == 2400.1
    assert stored_obj["ask"] == 2400.3
    assert stored_obj["mid"] == 2400.2

    msg = await asyncio.wait_for(
        pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0), 3.0
    )
    assert msg is not None
    payload = json.loads(msg["data"])
    assert payload["symbol"] == "XAUUSD"
    assert payload["mid"] == 2400.2

    await pubsub.unsubscribe(prices_channel("XAUUSD"))
    await pubsub.aclose()
    await redis.aclose()
