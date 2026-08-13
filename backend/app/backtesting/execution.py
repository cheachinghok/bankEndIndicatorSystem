"""Realistic order execution: spread, slippage, and SL/TP hit detection.

All prices are quoted as MID (what the signal engine sees). At execution
time we adjust for the fact that:
  - BUY orders fill at ASK  = mid + spread/2 + slippage
  - SELL orders fill at BID = mid - spread/2 - slippage
  - Stop-losses trigger at mid crossing SL, but fill even worse (slippage_sl)
  - Take-profits are limit orders — assumed to fill at the exact TP price

SL-first pessimistic rule: if a single candle's high/low touches both SL
and TP, we assume the STOP LOSS filled first. This is conservative and
appropriate — we can't tell from OHLC alone which came first.
"""
from app.backtesting.types import BacktestConfig, ExitReason
from app.services.market_data.models import Candle
from app.services.signals.types import SignalDirection


def apply_entry_fill(
    signal_price: float,
    direction: SignalDirection,
    config: BacktestConfig,
) -> float:
    """Convert the signal's mid-price entry into an actual fill price."""
    adverse = config.spread / 2 + config.slippage_entry
    if direction == SignalDirection.BUY:
        return signal_price + adverse
    return signal_price - adverse


def apply_sl_fill(
    sl_price: float,
    direction: SignalDirection,
    config: BacktestConfig,
) -> float:
    """SL is hit — actual fill is worse than the trigger price."""
    if direction == SignalDirection.BUY:
        return sl_price - config.slippage_sl  # fill below SL
    return sl_price + config.slippage_sl      # fill above SL


def check_bar_exit(
    candle: Candle,
    direction: SignalDirection,
    stop_loss: float,
    take_profit: float,
) -> ExitReason | None:
    """Return the exit reason if the bar hit SL or TP, else None.

    Pessimistic when both are within the bar's range: SL wins.
    """
    high, low = candle.high, candle.low
    if direction == SignalDirection.BUY:
        hit_sl = low <= stop_loss
        hit_tp = high >= take_profit
    else:  # SELL
        hit_sl = high >= stop_loss
        hit_tp = low <= take_profit

    if hit_sl and hit_tp:
        return ExitReason.SL      # pessimistic — assume SL fired first
    if hit_sl:
        return ExitReason.SL
    if hit_tp:
        return ExitReason.TP1
    return None
