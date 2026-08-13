from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BacktestRun


class BacktestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        symbol_code: str,
        config: dict,
        stats: dict,
        trades: list,
        equity_curve: list,
        initial_equity: float,
        final_equity: float,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> BacktestRun:
        row = BacktestRun(
            symbol_code=symbol_code,
            config=config,
            stats=stats,
            trades=trades,
            equity_curve=equity_curve,
            trade_count=len(trades),
            initial_equity=initial_equity,
            final_equity=final_equity,
            from_time=from_time,
            to_time=to_time,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get_by_id(self, run_id: int) -> BacktestRun | None:
        stmt = select(BacktestRun).where(BacktestRun.id == run_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50) -> list[BacktestRun]:
        stmt = select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
