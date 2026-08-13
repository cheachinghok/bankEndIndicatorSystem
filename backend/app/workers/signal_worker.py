"""Signal generation worker.

Listens on the Redis `candles:{symbol}:15m` channel (published by the candle
poller whenever a new closed 15m candle is inserted). On each event:
    1. Load the last N candles from Postgres for each required timeframe.
    2. Run analyze() on each.
    3. Run generate_signal() to get a BUY/SELL/WAIT.
    4. Insert into the `signals` table.
    5. Publish the serialized signal to `signals:{symbol}` for WS fanout.

Idempotency: the poller only publishes on NEW inserts (via ON CONFLICT DO
NOTHING → rowcount==0 case skips publish), so we shouldn't get duplicates
for the same closed candle. But we don't guarantee "exactly once" — a WAIT
or duplicate signal is not harmful.
"""
import asyncio
import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.redis import candles_channel, get_redis, signals_channel
from app.db.models import Symbol
from app.db.session import SessionLocal
from app.repositories.market_data import MarketDataRepository
from app.repositories.signals import SignalRepository
from app.services.analysis import analyze
from app.services.market_data.models import Candle, Timeframe
from app.services.signals import SignalDirection, SignalResult, generate_signal

log = logging.getLogger(__name__)

REQUIRED_TFS: tuple[Timeframe, ...] = ("4h", "1h", "15m")
OPTIONAL_TFS: tuple[Timeframe, ...] = ("5m",)
HISTORY_PER_TF = 500  # enough for EMA200 seed + buffer


def _serialize_signal(result: SignalResult, symbol: str) -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "timeframe": result.timeframe,
            "direction": result.direction.value,
            "confidence": result.confidence,
            "entry": result.entry,
            "stop_loss": result.stop_loss,
            "take_profit_1": result.take_profit_1,
            "take_profit_2": result.take_profit_2,
            "risk_reward": result.risk_reward,
            "reasons": result.reasons,
            "warnings": result.warnings,
            "breakdown": result.breakdown,
            "generated_at": (result.generated_at or datetime.now(UTC))
            .astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
    )


async def _load_recent_candles(
    session_factory: async_sessionmaker,
    symbol: str,
) -> dict[Timeframe, list[Candle]]:
    tfs = REQUIRED_TFS + OPTIONAL_TFS
    out: dict[Timeframe, list[Candle]] = {}
    async with session_factory() as session:
        repo = MarketDataRepository(session)
        for tf in tfs:
            rows = await repo.list_candles(symbol, tf, HISTORY_PER_TF)
            out[tf] = [
                Candle(
                    timestamp=r.timestamp,
                    open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
                )
                for r in rows
            ]
    return out


async def _handle_candle_event(
    session_factory: async_sessionmaker,
    redis: Redis,
    symbol: str,
) -> None:
    candles_by_tf = await _load_recent_candles(session_factory, symbol)

    # Skip if any required TF is empty or too short — trend needs 210+.
    for tf in REQUIRED_TFS:
        if len(candles_by_tf.get(tf, [])) < 210:
            log.info(
                "signal worker: skipping %s — %s has only %d candles (need ≥210)",
                symbol, tf, len(candles_by_tf.get(tf, [])),
            )
            return

    analyses = {tf: analyze(candles_by_tf[tf]) for tf in candles_by_tf if candles_by_tf[tf]}
    result = generate_signal(symbol, analyses)

    async with session_factory() as session:
        # Find the symbol row (created by candle poller).
        stmt = select(Symbol).where(Symbol.code == symbol.upper())
        sym_row = (await session.execute(stmt)).scalar_one_or_none()
        if sym_row is None:
            log.warning("signal worker: symbol %s not found in DB — cannot persist", symbol)
        else:
            await SignalRepository(session).insert(sym_row.id, result)

    await redis.publish(signals_channel(symbol), _serialize_signal(result, symbol))
    log.info(
        "signal generated: %s %s conf=%.1f (%s)",
        symbol, result.direction.value, result.confidence,
        result.reasons[0] if result.reasons else "no reasons",
    )


async def run_signal_worker(
    symbol: str,
    *,
    session_factory: async_sessionmaker | None = None,
    redis: Redis | None = None,
) -> None:
    """Run forever. Cancel to shut down cleanly."""
    owned_redis = redis is None
    redis = redis or get_redis()
    session_factory = session_factory or SessionLocal

    pubsub = redis.pubsub()
    channel = candles_channel(symbol, "15m")
    await pubsub.subscribe(channel)
    log.info("signal worker subscribed to %s", channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            try:
                await _handle_candle_event(session_factory, redis, symbol)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — worker must not die on any single failure
                log.exception("signal worker error while handling event: %r", e)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        if owned_redis:
            await redis.aclose()
