"""Technical indicators.

Pure-Python implementations (no numpy/pandas-ta dep) so results are
reproducible and easy to reason about in tests. Fast enough at MVP scale
(one symbol, a few timeframes, hundreds of candles per compute).

Public API:
    ema, ema_latest, IncrementalEMA
    rsi, rsi_latest
    macd, macd_latest, MacdResult
    atr, atr_latest
    closes, highs, lows           (Candle extractors)
"""
from app.services.indicators.atr import atr, atr_latest
from app.services.indicators.candles import closes, highs, lows
from app.services.indicators.ema import IncrementalEMA, ema, ema_latest
from app.services.indicators.macd import MacdResult, macd, macd_latest
from app.services.indicators.rsi import rsi, rsi_latest

__all__ = [
    "IncrementalEMA",
    "MacdResult",
    "atr",
    "atr_latest",
    "closes",
    "ema",
    "ema_latest",
    "highs",
    "lows",
    "macd",
    "macd_latest",
    "rsi",
    "rsi_latest",
]
