from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.market_data import MarketDataRepository
from app.services.market_data.models import TIMEFRAMES, Timeframe
from app.services.market_data.oanda_provider import OandaProvider, _to_provider_symbol

router = APIRouter()


class CandleResponse(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: list[CandleResponse]


@router.get("/{symbol}/candles", response_model=CandlesResponse)
async def get_candles(
    symbol: str,
    timeframe: Annotated[Timeframe, Query()] = "15m",
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CandlesResponse:
    symbol = symbol.upper()
    if timeframe not in TIMEFRAMES:
        raise HTTPException(400, f"Unsupported timeframe: {timeframe}")

    try:
        provider_code = _to_provider_symbol(symbol)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    repo = MarketDataRepository(session)
    rows = await repo.list_candles(symbol, timeframe, limit)

    if len(rows) < limit:
        if not settings.oanda_api_token:
            raise HTTPException(
                503,
                "No cached candles and OANDA_API_TOKEN is not configured — cannot backfill.",
            )
        provider = OandaProvider(
            api_token=settings.oanda_api_token,
            api_url=settings.oanda_api_url,
        )
        try:
            fresh = await provider.fetch_candles(symbol, timeframe, count=limit)
        finally:
            await provider.aclose()

        symbol_obj = await repo.get_or_create_symbol(symbol, provider_code)
        await repo.upsert_candles(symbol_obj.id, timeframe, fresh)
        rows = await repo.list_candles(symbol, timeframe, limit)

    return CandlesResponse(
        symbol=symbol,
        timeframe=timeframe,
        candles=[
            CandleResponse(
                timestamp=r.timestamp,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
            )
            for r in rows
        ],
    )
