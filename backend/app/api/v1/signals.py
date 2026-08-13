"""Signals REST endpoints."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Signal, Symbol
from app.db.session import get_session

router = APIRouter()


class SignalOut(BaseModel):
    id: int
    symbol: str
    timeframe: str
    direction: str
    confidence: float
    entry: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    risk_reward: float | None
    breakdown: dict
    reasons: list[str]
    warnings: list[str]
    generated_at: datetime


class SignalList(BaseModel):
    count: int
    signals: list[SignalOut]


def _row_to_out(sig: Signal, symbol_code: str) -> SignalOut:
    return SignalOut(
        id=sig.id,
        symbol=symbol_code,
        timeframe=sig.timeframe,
        direction=sig.direction,
        confidence=sig.confidence,
        entry=sig.entry,
        stop_loss=sig.stop_loss,
        take_profit_1=sig.take_profit_1,
        take_profit_2=sig.take_profit_2,
        risk_reward=sig.risk_reward,
        breakdown=sig.breakdown or {},
        reasons=sig.reasons or [],
        warnings=sig.warnings or [],
        generated_at=sig.generated_at,
    )


@router.get("", response_model=SignalList)
async def list_signals(
    symbol: Annotated[str | None, Query()] = None,
    min_confidence: Annotated[float, Query(ge=0.0, le=100.0)] = 0.0,
    direction: Annotated[str | None, Query(pattern="^(BUY|SELL|WAIT)$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    session: AsyncSession = Depends(get_session),
) -> SignalList:
    stmt = (
        select(Signal, Symbol.code)
        .join(Symbol, Symbol.id == Signal.symbol_id)
        .where(Signal.confidence >= min_confidence)
    )
    if symbol is not None:
        stmt = stmt.where(Symbol.code == symbol.upper())
    if direction is not None:
        stmt = stmt.where(Signal.direction == direction)
    stmt = stmt.order_by(Signal.generated_at.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = list(result.all())
    signals = [_row_to_out(sig, code) for sig, code in rows]
    return SignalList(count=len(signals), signals=signals)


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(
    signal_id: int,
    session: AsyncSession = Depends(get_session),
) -> SignalOut:
    stmt = (
        select(Signal, Symbol.code)
        .join(Symbol, Symbol.id == Signal.symbol_id)
        .where(Signal.id == signal_id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(404, f"Signal {signal_id} not found")
    sig, code = row
    return _row_to_out(sig, code)
