"""Backtest data types."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.services.signals.types import SignalDirection


class ExitReason(str, Enum):
    TP1 = "TP1"           # take-profit hit
    SL = "SL"             # stop-loss hit
    END_OF_DATA = "END"   # backtest ended with open position


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """XAUUSD-tuned defaults; override for other symbols or strategies."""
    initial_equity: float = 10_000.0
    risk_per_trade_pct: float = 1.0     # % of current equity at trade entry
    min_confidence: float = 60.0        # ignore signals below this

    # Execution realism (in price units — dollars for XAUUSD).
    spread: float = 0.30                # bid-ask spread
    slippage_entry: float = 0.20        # additional adverse fill on entry
    slippage_sl: float = 0.50           # additional adverse fill on stop-loss

    # Trade management.
    allow_pyramiding: bool = False      # if False, ignore new signals while a position is open


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    direction: SignalDirection          # BUY or SELL only (never WAIT)
    entry_time: datetime
    entry_price: float                  # after spread + slippage
    stop_loss: float
    take_profit: float
    position_size: float                # units of the base asset (oz for XAU)
    signal_confidence: float

    exit_time: datetime | None
    exit_price: float | None            # after adverse slippage on SL
    exit_reason: ExitReason | None

    pnl: float | None                   # in account currency
    pnl_r: float | None                 # in "R" multiples (1R = risk_amount)
    equity_before: float
    equity_after: float | None


@dataclass(frozen=True, slots=True)
class BacktestStats:
    total_trades: int
    wins: int
    losses: int
    win_rate: float                     # 0..1
    profit_factor: float                # gross_profit / gross_loss (inf if no losses)
    net_profit: float                   # currency
    net_profit_pct: float               # % of initial equity
    max_drawdown: float                 # currency
    max_drawdown_pct: float             # % of peak equity
    avg_win: float                      # currency
    avg_loss: float                     # currency (negative)
    avg_rr_realized: float              # in R multiples
    max_consecutive_losses: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    final_equity: float
    stats: BacktestStats
