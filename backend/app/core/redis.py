"""Redis client factory and pub/sub key/channel naming.

Keys/channels are centralized here so nothing else in the codebase hardcodes them.
"""
from redis.asyncio import Redis, from_url

from app.core.config import get_settings


def get_redis() -> Redis:
    """Return a new async Redis client. Callers must aclose() when done."""
    return from_url(get_settings().redis_url, decode_responses=True)


# Key naming
def latest_price_key(symbol: str) -> str:
    return f"price:{symbol.upper()}"


# Channel naming
def prices_channel(symbol: str) -> str:
    return f"prices:{symbol.upper()}"


def candles_channel(symbol: str, timeframe: str) -> str:
    return f"candles:{symbol.upper()}:{timeframe}"


def signals_channel(symbol: str) -> str:
    return f"signals:{symbol.upper()}"
