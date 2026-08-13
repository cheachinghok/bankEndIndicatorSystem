from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Signal, Symbol
from app.services.signals.types import SignalResult


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, symbol_id: int, result: SignalResult) -> Signal:
        row = Signal(
            symbol_id=symbol_id,
            timeframe=result.timeframe,
            direction=result.direction.value,
            confidence=result.confidence,
            entry=result.entry,
            stop_loss=result.stop_loss,
            take_profit_1=result.take_profit_1,
            take_profit_2=result.take_profit_2,
            risk_reward=result.risk_reward,
            breakdown=result.breakdown,
            reasons=result.reasons,
            warnings=result.warnings,
            generated_at=result.generated_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_recent(self, limit: int = 50) -> list[Signal]:
        stmt = select(Signal).order_by(Signal.generated_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_symbol(self, symbol_code: str, limit: int = 50) -> list[Signal]:
        stmt = (
            select(Signal)
            .join(Symbol, Symbol.id == Signal.symbol_id)
            .where(Symbol.code == symbol_code)
            .order_by(Signal.generated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
