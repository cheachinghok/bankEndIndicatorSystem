"""WebSocket endpoint for live market data.

Clients connect to /ws/market/{symbol} and receive JSON messages of the form:

    {"type": "price", ...tick fields...}
    {"type": "candle", "timeframe": "15m", ...candle fields...}

Under the hood we subscribe to Redis channels: prices:{symbol} and
candles:{symbol}:* (one channel per timeframe). No auth in Phase 2 — that
comes in Phase 10.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import candles_channel, get_redis, prices_channel, signals_channel
from app.services.market_data.models import TIMEFRAMES
from app.services.market_data.oanda_provider import _to_provider_symbol

router = APIRouter()

log = logging.getLogger(__name__)


@router.websocket("/market/{symbol}")
async def market_ws(websocket: WebSocket, symbol: str) -> None:
    symbol = symbol.upper()
    try:
        _to_provider_symbol(symbol)  # validate
    except ValueError:
        await websocket.close(code=1008, reason=f"unsupported symbol: {symbol}")
        return

    await websocket.accept()
    redis = get_redis()
    pubsub = redis.pubsub()
    channels = [
        prices_channel(symbol),
        signals_channel(symbol),
        *(candles_channel(symbol, tf) for tf in TIMEFRAMES),
    ]
    await pubsub.subscribe(*channels)

    async def forward() -> None:
        # Use get_message() with a short timeout rather than pubsub.listen():
        # listen() has known hangs on redis-py async and gives no cancellation
        # checkpoints, so a client disconnect can't cleanly cancel this task.
        log.info("ws forwarder started for %s on channels=%s", symbol, channels)
        forwarded = 0
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            channel = message["channel"]
            data = message["data"]
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
            if channel.startswith("prices:"):
                payload = {"type": "price", **payload}
            elif channel.startswith("candles:"):
                payload = {"type": "candle", **payload}
            elif channel.startswith("signals:"):
                payload = {"type": "signal", **payload}
            await websocket.send_json(payload)
            forwarded += 1
            if forwarded == 1:
                log.info("ws %s: first message forwarded (channel=%s)", symbol, channel)

    forward_task = asyncio.create_task(forward())
    try:
        # We don't currently consume any client messages, but reading keeps the
        # connection alive and detects client-side disconnects promptly.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        log.warning("ws error for %s: %r", symbol, e)
    finally:
        forward_task.cancel()
        try:
            await forward_task
        except (asyncio.CancelledError, Exception):
            pass
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        await redis.aclose()
