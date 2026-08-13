"""Backtesting engine.

Walk-forward simulation of the exact same `generate_signal` engine used
live, on historical candles. Strict no-look-ahead: at candle t the engine
may only see candles [0..t].

Public API:
    BacktestConfig, BacktestResult, BacktestStats, Trade
    run_backtest(candles_by_tf, symbol, config) → BacktestResult
"""
from app.backtesting.engine import run_backtest
from app.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    BacktestStats,
    ExitReason,
    Trade,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BacktestStats",
    "ExitReason",
    "Trade",
    "run_backtest",
]
