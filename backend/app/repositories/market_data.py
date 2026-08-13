from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MarketData, Symbol
from app.services.market_data.models import Candle, Timeframe


class MarketDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_symbol(self, code: str, provider_code: str) -> Symbol:
        stmt = select(Symbol).where(Symbol.code == code)
        result = await self._session.execute(stmt)
        symbol = result.scalar_one_or_none()
        if symbol is not None:
            return symbol
        symbol = Symbol(code=code, provider_code=provider_code)
        self._session.add(symbol)
        await self._session.flush()
        return symbol

    async def upsert_candles(
        self, symbol_id: int, timeframe: Timeframe, candles: list[Candle]
    ) -> int:
        if not candles:
            return 0
        rows = [
            {
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
        stmt = pg_insert(MarketData).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_market_data_ohlc",
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

    async def list_candles(
        self, symbol_code: str, timeframe: Timeframe, limit: int
    ) -> list[MarketData]:
        stmt = (
            select(MarketData)
            .join(Symbol, Symbol.id == MarketData.symbol_id)
            .where(Symbol.code == symbol_code, MarketData.timeframe == timeframe)
            .order_by(MarketData.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()  # return chronological ascending
        return rows

    async def list_candles_range(
        self,
        symbol_code: str,
        timeframe: Timeframe,
        from_time: "datetime | None" = None,
        to_time: "datetime | None" = None,
    ) -> list[MarketData]:
        stmt = (
            select(MarketData)
            .join(Symbol, Symbol.id == MarketData.symbol_id)
            .where(Symbol.code == symbol_code, MarketData.timeframe == timeframe)
        )
        if from_time is not None:
            stmt = stmt.where(MarketData.timestamp >= from_time)
        if to_time is not None:
            stmt = stmt.where(MarketData.timestamp <= to_time)
        stmt = stmt.order_by(MarketData.timestamp.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
