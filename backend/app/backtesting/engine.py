"""Backtest walk-forward engine.

Master clock = 15m candles (the signal engine's primary decision timeframe).
At each 15m close t:
    1. Slice each TF's candles to only those closed at or before t (no look-ahead).
    2. Run the analysis engine on each TF.
    3. Run the signal engine.
    4. If we have an open position: check whether THIS 15m bar hit SL or TP.
       Exit if so (using the same 15m OHLC — pessimistic SL-first rule).
    5. If no open position AND signal is actionable AND confidence >= threshold:
       open a new position on the NEXT 15m bar's open.

Assumptions / limitations (documented so they're not silent):
    - One symbol at a time. No portfolio-level correlation modeling.
    - Full exit at TP1. TP2 is not modeled as a partial exit in this MVP.
    - Intra-15m execution is approximated by 15m OHLC. A finer 5m execution
      check would be more accurate for tight stops.
    - Weekend / market-closed candles are still iterated — OANDA doesn't
      emit candles when the market is closed, so this shouldn't matter,
      but be aware.
"""
from collections.abc import Sequence
from datetime import datetime

from app.backtesting.alignment import align_all_timeframes, timeframe_duration
from app.backtesting.execution import apply_entry_fill, apply_sl_fill, check_bar_exit
from app.backtesting.portfolio import Portfolio, position_size
from app.backtesting.stats import compute_stats
from app.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    ExitReason,
    Trade,
)
from app.services.analysis import analyze
from app.services.analysis.trend import MIN_HISTORY as TREND_MIN_HISTORY
from app.services.market_data.models import Candle, Timeframe
from app.services.signals import SignalDirection, generate_signal

PRIMARY_TF: Timeframe = "15m"
REQUIRED_TFS: tuple[Timeframe, ...] = ("4h", "1h", "15m")


def _make_pending_trade(
    symbol: str,
    direction: SignalDirection,
    entry_time: datetime,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    size: float,
    confidence: float,
    equity_before: float,
) -> Trade:
    return Trade(
        symbol=symbol,
        direction=direction,
        entry_time=entry_time,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=size,
        signal_confidence=confidence,
        exit_time=None,
        exit_price=None,
        exit_reason=None,
        pnl=None,
        pnl_r=None,
        equity_before=equity_before,
        equity_after=None,
    )


def _close_trade(
    trade: Trade,
    exit_time: datetime,
    exit_price: float,
    reason: ExitReason,
    equity_after: float,
) -> Trade:
    if trade.direction == SignalDirection.BUY:
        pnl = (exit_price - trade.entry_price) * trade.position_size
    else:
        pnl = (trade.entry_price - exit_price) * trade.position_size
    risk_amount = trade.equity_before - equity_after + pnl if pnl < 0 else abs(
        (trade.entry_price - trade.stop_loss) * trade.position_size
    )
    # More directly: risk_amount = |entry - stop_loss| * size
    risk_amount = abs(trade.entry_price - trade.stop_loss) * trade.position_size
    pnl_r = pnl / risk_amount if risk_amount > 0 else 0.0
    return Trade(
        symbol=trade.symbol,
        direction=trade.direction,
        entry_time=trade.entry_time,
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        position_size=trade.position_size,
        signal_confidence=trade.signal_confidence,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=reason,
        pnl=pnl,
        pnl_r=pnl_r,
        equity_before=trade.equity_before,
        equity_after=equity_after,
    )


def run_backtest(
    candles_by_tf: dict[Timeframe, Sequence[Candle]],
    symbol: str,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    config = config or BacktestConfig()

    for tf in REQUIRED_TFS:
        if tf not in candles_by_tf:
            raise ValueError(f"Missing required timeframe '{tf}' in candles_by_tf")

    primary = list(candles_by_tf[PRIMARY_TF])
    if len(primary) < TREND_MIN_HISTORY:
        raise ValueError(
            f"Not enough {PRIMARY_TF} history for backtest "
            f"(need ≥{TREND_MIN_HISTORY}, got {len(primary)})"
        )

    portfolio = Portfolio(initial_equity=config.initial_equity)
    trades: list[Trade] = []
    open_trade: Trade | None = None

    primary_duration = timeframe_duration(PRIMARY_TF)

    for i, candle in enumerate(primary):
        close_time = candle.timestamp + primary_duration

        # (1) If a trade is open, check whether THIS candle exited it.
        if open_trade is not None:
            reason = check_bar_exit(
                candle,
                open_trade.direction,
                open_trade.stop_loss,
                open_trade.take_profit,
            )
            if reason is not None:
                if reason == ExitReason.SL:
                    exit_price = apply_sl_fill(open_trade.stop_loss, open_trade.direction, config)
                else:
                    exit_price = open_trade.take_profit
                if open_trade.direction == SignalDirection.BUY:
                    pnl = (exit_price - open_trade.entry_price) * open_trade.position_size
                else:
                    pnl = (open_trade.entry_price - exit_price) * open_trade.position_size
                new_equity = portfolio.equity + pnl
                closed = _close_trade(open_trade, close_time, exit_price, reason, new_equity)
                trades.append(closed)
                portfolio.record(close_time, new_equity)
                open_trade = None

        # Record equity each bar even without trades so drawdown tracks correctly.
        if open_trade is None:
            portfolio.record(close_time, portfolio.equity)

        # (2) Look for a new signal at this close time.
        if open_trade is not None and not config.allow_pyramiding:
            continue

        analyses_candles = align_all_timeframes(candles_by_tf, close_time)
        # Skip if any required TF doesn't have enough history yet.
        if any(len(analyses_candles.get(tf, [])) < TREND_MIN_HISTORY for tf in REQUIRED_TFS):
            continue

        analyses = {tf: analyze(analyses_candles[tf]) for tf in analyses_candles}
        signal = generate_signal(symbol, analyses)
        if signal.direction == SignalDirection.WAIT:
            continue
        if signal.confidence < config.min_confidence:
            continue

        # (3) Open a new position on the NEXT 15m bar's open (realistic — we can't
        # trade instantly at the current bar's close).
        if i + 1 >= len(primary):
            continue  # no next bar to open on
        next_candle = primary[i + 1]
        entry_price = apply_entry_fill(next_candle.open, signal.direction, config)

        # Apply spread offset to SL/TP too so distances stay consistent with fill price.
        if signal.direction == SignalDirection.BUY:
            sl = signal.stop_loss + (entry_price - signal.entry) if signal.stop_loss else next_candle.open
            tp = signal.take_profit_1 + (entry_price - signal.entry) if signal.take_profit_1 else next_candle.open
        else:
            sl = signal.stop_loss + (entry_price - signal.entry) if signal.stop_loss else next_candle.open
            tp = signal.take_profit_1 + (entry_price - signal.entry) if signal.take_profit_1 else next_candle.open

        stop_distance = abs(entry_price - sl)
        size = position_size(portfolio.equity, config.risk_per_trade_pct, stop_distance)
        if size <= 0:
            continue

        open_trade = _make_pending_trade(
            symbol=symbol,
            direction=signal.direction,
            entry_time=next_candle.timestamp,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            size=size,
            confidence=signal.confidence,
            equity_before=portfolio.equity,
        )

    # Force-close any still-open trade at the last candle.
    if open_trade is not None and primary:
        last = primary[-1]
        exit_price = last.close
        if open_trade.direction == SignalDirection.BUY:
            pnl = (exit_price - open_trade.entry_price) * open_trade.position_size
        else:
            pnl = (open_trade.entry_price - exit_price) * open_trade.position_size
        new_equity = portfolio.equity + pnl
        closed = _close_trade(
            open_trade,
            last.timestamp + primary_duration,
            exit_price,
            ExitReason.END_OF_DATA,
            new_equity,
        )
        trades.append(closed)
        portfolio.record(last.timestamp + primary_duration, new_equity)

    stats = compute_stats(
        trades=trades,
        initial_equity=config.initial_equity,
        final_equity=portfolio.equity,
        max_drawdown=portfolio.max_drawdown,
        peak_equity=portfolio.peak,
    )

    return BacktestResult(
        symbol=symbol,
        config=config,
        trades=trades,
        equity_curve=portfolio.curve,
        final_equity=portfolio.equity,
        stats=stats,
    )
