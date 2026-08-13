"""Live price streaming worker.

Consumes the OANDA pricing stream, publishes each PriceTick to Redis pub/sub,
and caches the latest tick per symbol as a JSON string with a short TTL.

Reconnect strategy: exponential backoff from 1s to 60s, resetting after any
successful message. HTTP 401 stops the worker (bad credentials — no point retrying).
"""
import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis

from app.core.redis import get_redis, latest_price_key, prices_channel
from app.services.market_data.models import PriceTick
from app.services.market_data.provider import StreamingMarketDataProvider

log = logging.getLogger(__name__)

LATEST_PRICE_TTL_SECONDS = 30
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0
HEARTBEAT_WATCHDOG_SECONDS = 15.0


def _tick_to_json(tick: PriceTick) -> str:
    return json.dumps(
        {
            "symbol": tick.symbol,
            "timestamp": tick.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "bid": tick.bid,
            "ask": tick.ask,
            "mid": tick.mid,
            "tradeable": tick.tradeable,
        }
    )


async def _publish_tick(redis: Redis, tick: PriceTick) -> None:
    payload = _tick_to_json(tick)
    await redis.set(latest_price_key(tick.symbol), payload, ex=LATEST_PRICE_TTL_SECONDS)
    await redis.publish(prices_channel(tick.symbol), payload)


async def _stream_once(
    provider: StreamingMarketDataProvider,
    redis: Redis,
    symbols: list[str],
) -> None:
    """Consume the stream until it ends, raises, or the watchdog fires.

    The watchdog and the consumer run as sibling tasks; whichever completes
    first cancels the other. Previously the watchdog raised inside its own
    task and never interrupted the consumer — a silent stream would hang forever.
    """
    last_tick_at = asyncio.get_event_loop().time()
    tick_count = 0

    async def consume() -> None:
        nonlocal last_tick_at, tick_count
        async for tick in provider.stream_prices(symbols):
            last_tick_at = asyncio.get_event_loop().time()
            if tick_count == 0:
                log.info("first tick received: %s bid=%.4f ask=%.4f", tick.symbol, tick.bid, tick.ask)
            tick_count += 1
            await _publish_tick(redis, tick)

    async def watchdog() -> None:
        while True:
            await asyncio.sleep(1.0)
            idle = asyncio.get_event_loop().time() - last_tick_at
            if idle > HEARTBEAT_WATCHDOG_SECONDS:
                log.warning(
                    "stream watchdog: %.1fs since last tick (received %d so far), forcing reconnect",
                    idle,
                    tick_count,
                )
                raise TimeoutError("no ticks within heartbeat window")

    consume_task = asyncio.create_task(consume(), name="stream_consume")
    watchdog_task = asyncio.create_task(watchdog(), name="stream_watchdog")
    try:
        done, _ = await asyncio.wait(
            {consume_task, watchdog_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Re-raise the completed task's exception (if any) so the outer
        # reconnect loop can log and back off.
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
    finally:
        for task in (consume_task, watchdog_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(consume_task, watchdog_task, return_exceptions=True)


async def run_price_stream(
    provider: StreamingMarketDataProvider,
    symbols: list[str],
    *,
    redis: Redis | None = None,
) -> None:
    """Run the price stream forever with exponential-backoff reconnects.

    Cancel this coroutine to shut down cleanly.
    """
    owned_redis = redis is None
    redis = redis or get_redis()
    backoff = INITIAL_BACKOFF
    try:
        while True:
            started_at = datetime.now(UTC)
            try:
                log.info("connecting price stream for %s", symbols)
                await _stream_once(provider, redis, symbols)
                log.info("price stream ended cleanly, reconnecting")
                backoff = INITIAL_BACKOFF
            except asyncio.CancelledError:
                raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    log.error("auth failed on price stream (%s); stopping worker", e.response.status_code)
                    raise
                log.warning("price stream HTTP error: %s — retrying in %.1fs", e, backoff)
            except Exception as e:  # noqa: BLE001 — worker must not die on any single error
                # Reset backoff if we managed to stay connected for a while.
                if (datetime.now(UTC) - started_at).total_seconds() > 30:
                    backoff = INITIAL_BACKOFF
                log.warning("price stream error: %r — retrying in %.1fs", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
    finally:
        if owned_redis:
            await redis.aclose()
