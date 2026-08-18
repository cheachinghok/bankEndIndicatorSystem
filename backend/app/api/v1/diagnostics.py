"""Signal diagnostics — 'why is my signal WAIT right now?'

Runs the full analysis + signal engine on demand against the latest DB
candles and returns the per-timeframe state plus the gate/pullback
decision.  Handy for debugging why signals aren't firing and for
building a 'Why no signal?' UI later.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.market_data import MarketDataRepository
from app.services.analysis import analyze
from app.services.market_data.models import Candle, Timeframe
from app.services.signals import generate_signal
from app.services.signals.rules import (
    check_pullback,
    multi_timeframe_gate,
)

router = APIRouter()

_TFS: tuple[Timeframe, ...] = ("4h", "1h", "15m", "5m")
_HISTORY = 500


class TimeframeDiag(BaseModel):
    timeframe: str
    candle_count: int
    latest_close: float | None
    direction: str
    aggregate_score: float
    trend_direction: str
    trend_score: float
    momentum_direction: str
    momentum_rsi: float
    momentum_macd: float
    structure_direction: str
    structure_score: float
    volatility_level: str
    volatility_atr: float


class DiagnosticsResponse(BaseModel):
    symbol: str
    generated_at: datetime
    timeframes: list[TimeframeDiag]
    gate_direction: str
    gate_reason: str
    pullback_direction: str | None
    pullback_reason: str | None
    signal_direction: str
    signal_confidence: float


@router.get("/{symbol}", response_model=DiagnosticsResponse)
async def diagnostics(
    symbol: str,
    session: AsyncSession = Depends(get_session),
) -> DiagnosticsResponse:
    symbol = symbol.upper()
    repo = MarketDataRepository(session)

    candles_by_tf: dict[Timeframe, list[Candle]] = {}
    for tf in _TFS:
        rows = await repo.list_candles(symbol, tf, _HISTORY)
        candles_by_tf[tf] = [
            Candle(
                timestamp=r.timestamp,
                open=r.open, high=r.high, low=r.low, close=r.close,
                volume=r.volume,
            )
            for r in rows
        ]

    if all(len(cs) == 0 for cs in candles_by_tf.values()):
        raise HTTPException(
            404,
            f"No candles in DB for {symbol}. Backfill via /market/{symbol}/candles.",
        )

    analyses = {
        tf: analyze(candles_by_tf[tf])
        for tf in candles_by_tf
        if candles_by_tf[tf]
    }

    gate = multi_timeframe_gate(analyses)
    pullback = check_pullback(analyses)
    signal = generate_signal(symbol, analyses)

    tf_diags: list[TimeframeDiag] = []
    for tf in _TFS:
        candles = candles_by_tf.get(tf, [])
        a = analyses.get(tf)
        if a is None:
            tf_diags.append(
                TimeframeDiag(
                    timeframe=tf,
                    candle_count=len(candles),
                    latest_close=candles[-1].close if candles else None,
                    direction="NEUTRAL",
                    aggregate_score=0.0,
                    trend_direction="NEUTRAL",
                    trend_score=0.0,
                    momentum_direction="NEUTRAL",
                    momentum_rsi=0.0,
                    momentum_macd=0.0,
                    structure_direction="NEUTRAL",
                    structure_score=0.0,
                    volatility_level="UNKNOWN",
                    volatility_atr=0.0,
                )
            )
            continue
        tf_diags.append(
            TimeframeDiag(
                timeframe=tf,
                candle_count=len(candles),
                latest_close=candles[-1].close if candles else None,
                direction=a.direction.value,
                aggregate_score=round(a.score, 2),
                trend_direction=a.trend.direction.value,
                trend_score=round(a.trend.score, 2),
                momentum_direction=a.momentum.direction.value,
                momentum_rsi=round(a.momentum.rsi, 2)
                if a.momentum.rsi == a.momentum.rsi else 0.0,
                momentum_macd=round(a.momentum.macd, 4)
                if a.momentum.macd == a.momentum.macd else 0.0,
                structure_direction=a.structure.direction.value,
                structure_score=round(a.structure.score, 2),
                volatility_level=a.volatility.level,
                volatility_atr=round(a.volatility.atr, 4)
                if a.volatility.atr == a.volatility.atr else 0.0,
            )
        )

    return DiagnosticsResponse(
        symbol=symbol,
        generated_at=signal.generated_at or datetime.utcnow(),
        timeframes=tf_diags,
        gate_direction=gate.direction.value,
        gate_reason=gate.reason,
        pullback_direction=pullback.direction.value if pullback else None,
        pullback_reason=pullback.reason if pullback else None,
        signal_direction=signal.direction.value,
        signal_confidence=signal.confidence,
    )
