"""Backtest orchestration.

Loads historical candles from Postgres, runs the backtest engine in a
thread (it's CPU-bound sync — must not block the event loop), and returns
a serialized result ready to store in the DB.
"""
import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting import BacktestConfig, run_backtest
from app.backtesting.types import BacktestResult
from app.repositories.market_data import MarketDataRepository
from app.services.market_data.models import Candle, Timeframe

REQUIRED_TFS: tuple[Timeframe, ...] = ("4h", "1h", "15m")


class NotEnoughDataError(RuntimeError):
    pass


async def load_candles(
    session: AsyncSession,
    symbol: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> dict[Timeframe, list[Candle]]:
    repo = MarketDataRepository(session)
    out: dict[Timeframe, list[Candle]] = {}
    for tf in REQUIRED_TFS:
        rows = await repo.list_candles_range(symbol, tf, from_time=from_time, to_time=to_time)
        out[tf] = [
            Candle(
                timestamp=r.timestamp,
                open=r.open, high=r.high, low=r.low, close=r.close,
                volume=r.volume,
            )
            for r in rows
        ]
    return out


async def execute_backtest(
    session: AsyncSession,
    symbol: str,
    config: BacktestConfig,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> BacktestResult:
    candles = await load_candles(session, symbol, from_time=from_time, to_time=to_time)

    empty_tfs = [tf for tf, cs in candles.items() if not cs]
    if empty_tfs:
        raise NotEnoughDataError(
            f"No candles in DB for {symbol} on timeframe(s): {', '.join(empty_tfs)}. "
            "Let the candle poller run for a while, or backfill via the /market endpoint."
        )

    # run_backtest is CPU-bound sync; offload to a thread so we don't block the loop.
    return await asyncio.to_thread(run_backtest, candles, symbol, config)


def serialize_result(result: BacktestResult) -> dict[str, Any]:
    """Convert a BacktestResult into JSON-safe dicts for persistence.

    Datetimes are ISO strings. Enums are their value.
    """
    def _dt(d: datetime | None) -> str | None:
        return d.isoformat() if d else None

    trades = [
        {
            **{k: v for k, v in asdict(t).items()
               if k not in ("entry_time", "exit_time", "direction", "exit_reason")},
            "entry_time": _dt(t.entry_time),
            "exit_time": _dt(t.exit_time),
            "direction": t.direction.value,
            "exit_reason": t.exit_reason.value if t.exit_reason else None,
        }
        for t in result.trades
    ]
    equity_curve = [(_dt(ts), eq) for ts, eq in result.equity_curve]
    return {
        "config": asdict(result.config),
        "stats": asdict(result.stats),
        "trades": trades,
        "equity_curve": equity_curve,
        "final_equity": result.final_equity,
    }
