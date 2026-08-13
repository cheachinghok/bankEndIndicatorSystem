"""Candle poller — periodically fetches closed candles for each timeframe
and upserts them to Postgres. Publishes newly-inserted candles to Redis so
WebSocket subscribers get pushed the closed candle as soon as we see it.

Poll cadence: every 30s. OANDA's candles endpoint is cheap, and we ask for
only the last ~3 candles per timeframe per tick, so this is well within
rate limits (100 req/sec on OANDA v20 practice).
"""
import asyncio
import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.redis import candles_channel, get_redis
from app.db.session import SessionLocal
from app.repositories.market_data import MarketDataRepository
from app.services.market_data.models import TIMEFRAMES, Candle, Timeframe
from app.services.market_data.oanda_provider import _to_provider_symbol
from app.services.market_data.provider import MarketDataProvider

log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30.0
FETCH_COUNT_PER_POLL = 3  # closed + in-flight, provider already drops in-flight


def _candle_to_json(candle: Candle, timeframe: Timeframe, symbol: str) -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": candle.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
    )


async def _poll_symbol(
    provider: MarketDataProvider,
    session_factory: async_sessionmaker,
    redis: Redis,
    symbol: str,
    timeframes: tuple[Timeframe, ...],
) -> None:
    provider_code = _to_provider_symbol(symbol)
    for tf in timeframes:
        try:
            fresh = await provider.fetch_candles(symbol, tf, count=FETCH_COUNT_PER_POLL)
        except Exception as e:  # noqa: BLE001
            log.warning("candle poll fetch failed for %s %s: %r", symbol, tf, e)
            continue
        if not fresh:
            continue

        async with session_factory() as session:
            repo = MarketDataRepository(session)
            sym = await repo.get_or_create_symbol(symbol, provider_code)
            inserted = await repo.upsert_candles(sym.id, tf, fresh)

        if inserted:
            # Publish the newest candle (last one) since it's the one that just closed.
            latest = fresh[-1]
            await redis.publish(candles_channel(symbol, tf), _candle_to_json(latest, tf, symbol))
            log.info(
                "poll %s %s: inserted %d, newest ts=%s close=%.4f",
                symbol,
                tf,
                inserted,
                latest.timestamp.isoformat(),
                latest.close,
            )


async def run_candle_poller(
    provider: MarketDataProvider,
    symbols: list[str],
    *,
    timeframes: tuple[Timeframe, ...] = TIMEFRAMES,
    redis: Redis | None = None,
    session_factory: async_sessionmaker | None = None,
    interval: float = POLL_INTERVAL_SECONDS,
) -> None:
    """Run the candle poller forever. Cancel to shut down cleanly."""
    owned_redis = redis is None
    redis = redis or get_redis()
    session_factory = session_factory or SessionLocal
    try:
        while True:
            start = asyncio.get_event_loop().time()
            for symbol in symbols:
                try:
                    await _poll_symbol(provider, session_factory, redis, symbol, timeframes)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    log.warning("candle poller loop error for %s: %r", symbol, e)
            elapsed = asyncio.get_event_loop().time() - start
            await asyncio.sleep(max(0.0, interval - elapsed))
    finally:
        if owned_redis:
            await redis.aclose()
