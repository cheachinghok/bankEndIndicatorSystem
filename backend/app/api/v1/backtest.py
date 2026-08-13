"""Backtest REST endpoints."""
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting import BacktestConfig
from app.db.session import get_session
from app.repositories.backtests import BacktestRepository
from app.services.backtesting.service import (
    NotEnoughDataError,
    execute_backtest,
    serialize_result,
)

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="e.g. XAUUSD")
    from_time: datetime | None = None
    to_time: datetime | None = None
    initial_equity: float = Field(default=10_000.0, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=100.0)
    min_confidence: float = Field(default=60.0, ge=0.0, le=100.0)
    spread: float = Field(default=0.30, ge=0.0)
    slippage_entry: float = Field(default=0.20, ge=0.0)
    slippage_sl: float = Field(default=0.50, ge=0.0)


class BacktestSummary(BaseModel):
    id: int
    symbol: str
    trade_count: int
    initial_equity: float
    final_equity: float
    net_profit_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    from_time: datetime | None
    to_time: datetime | None
    created_at: datetime


class BacktestDetail(BacktestSummary):
    config: dict[str, Any]
    stats: dict[str, Any]
    trades: list[dict[str, Any]]
    equity_curve: list[tuple[datetime | None, float]]


def _summary_from_row(row) -> BacktestSummary:
    stats = row.stats or {}
    return BacktestSummary(
        id=row.id,
        symbol=row.symbol_code,
        trade_count=row.trade_count,
        initial_equity=row.initial_equity,
        final_equity=row.final_equity,
        net_profit_pct=stats.get("net_profit_pct", 0.0),
        win_rate=stats.get("win_rate", 0.0),
        profit_factor=stats.get("profit_factor", 0.0),
        max_drawdown_pct=stats.get("max_drawdown_pct", 0.0),
        from_time=row.from_time,
        to_time=row.to_time,
        created_at=row.created_at,
    )


@router.post("", response_model=BacktestDetail)
async def submit_backtest(
    req: BacktestRequest,
    session: AsyncSession = Depends(get_session),
) -> BacktestDetail:
    symbol = req.symbol.upper()
    config = BacktestConfig(
        initial_equity=req.initial_equity,
        risk_per_trade_pct=req.risk_per_trade_pct,
        min_confidence=req.min_confidence,
        spread=req.spread,
        slippage_entry=req.slippage_entry,
        slippage_sl=req.slippage_sl,
    )
    try:
        result = await execute_backtest(
            session, symbol, config, from_time=req.from_time, to_time=req.to_time
        )
    except NotEnoughDataError as e:
        raise HTTPException(400, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    payload = serialize_result(result)
    repo = BacktestRepository(session)
    row = await repo.insert(
        symbol_code=symbol,
        config=payload["config"],
        stats=payload["stats"],
        trades=payload["trades"],
        equity_curve=payload["equity_curve"],
        initial_equity=config.initial_equity,
        final_equity=result.final_equity,
        from_time=req.from_time,
        to_time=req.to_time,
    )

    return BacktestDetail(
        **_summary_from_row(row).model_dump(),
        config=row.config,
        stats=row.stats,
        trades=row.trades,
        equity_curve=row.equity_curve,
    )


@router.get("/{run_id}", response_model=BacktestDetail)
async def get_backtest(
    run_id: int,
    session: AsyncSession = Depends(get_session),
) -> BacktestDetail:
    repo = BacktestRepository(session)
    row = await repo.get_by_id(run_id)
    if row is None:
        raise HTTPException(404, f"Backtest run {run_id} not found")
    return BacktestDetail(
        **_summary_from_row(row).model_dump(),
        config=row.config,
        stats=row.stats,
        trades=row.trades,
        equity_curve=row.equity_curve,
    )


@router.get("", response_model=list[BacktestSummary])
async def list_backtests(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    session: AsyncSession = Depends(get_session),
) -> list[BacktestSummary]:
    repo = BacktestRepository(session)
    rows = await repo.list_recent(limit)
    return [_summary_from_row(r) for r in rows]
