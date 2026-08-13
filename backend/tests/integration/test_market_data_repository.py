"""Integration test — requires running Postgres at DATABASE_URL.

Run:
    docker compose up -d
    alembic upgrade head
    pytest tests/integration
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.repositories.market_data import MarketDataRepository
from app.services.market_data.models import Candle


@pytest.mark.asyncio
async def test_upsert_and_list_candles_roundtrip() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    base = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    candles = [
        Candle(
            timestamp=base + timedelta(minutes=15 * i),
            open=2400.0 + i,
            high=2402.0 + i,
            low=2399.0 + i,
            close=2401.0 + i,
            volume=100 + i,
        )
        for i in range(5)
    ]

    async with SessionLocal() as session:
        repo = MarketDataRepository(session)
        symbol = await repo.get_or_create_symbol("XAUUSD_TEST", "XAU_USD")
        inserted = await repo.upsert_candles(symbol.id, "15m", candles)
        assert inserted == 5

        # idempotent upsert
        inserted_again = await repo.upsert_candles(symbol.id, "15m", candles)
        assert inserted_again == 0

        rows = await repo.list_candles("XAUUSD_TEST", "15m", limit=10)
        assert len(rows) == 5
        assert rows[0].timestamp == base
        assert rows[-1].close == 2405.0

    await engine.dispose()
