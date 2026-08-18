from fastapi import APIRouter

from app.api.v1 import backtest, diagnostics, market, signals, ws

api_router = APIRouter()
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_router.include_router(
    diagnostics.router, prefix="/signals/diagnostics", tags=["diagnostics"]
)
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
