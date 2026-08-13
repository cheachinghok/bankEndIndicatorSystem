"""Aggregate stats from a list of closed trades."""
import math

from app.backtesting.types import BacktestStats, Trade


def compute_stats(
    trades: list[Trade],
    initial_equity: float,
    final_equity: float,
    max_drawdown: float,
    peak_equity: float,
) -> BacktestStats:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return BacktestStats(
            total_trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            profit_factor=0.0,
            net_profit=final_equity - initial_equity,
            net_profit_pct=(final_equity - initial_equity) / initial_equity * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=(max_drawdown / peak_equity * 100) if peak_equity > 0 else 0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_rr_realized=0.0,
            max_consecutive_losses=0,
        )

    wins = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) <= 0]
    win_count = len(wins)
    loss_count = len(losses)

    gross_profit = sum(t.pnl for t in wins if t.pnl is not None)
    gross_loss = -sum(t.pnl for t in losses if t.pnl is not None)  # positive number
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else math.inf

    avg_win = gross_profit / win_count if win_count else 0.0
    avg_loss = -gross_loss / loss_count if loss_count else 0.0

    rr_values = [t.pnl_r for t in closed if t.pnl_r is not None]
    avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0

    max_streak = _max_consecutive_losses(closed)

    net_profit = final_equity - initial_equity
    return BacktestStats(
        total_trades=len(closed),
        wins=win_count,
        losses=loss_count,
        win_rate=win_count / len(closed),
        profit_factor=profit_factor,
        net_profit=net_profit,
        net_profit_pct=net_profit / initial_equity * 100,
        max_drawdown=max_drawdown,
        max_drawdown_pct=(max_drawdown / peak_equity * 100) if peak_equity > 0 else 0.0,
        avg_win=avg_win,
        avg_loss=avg_loss,
        avg_rr_realized=avg_rr,
        max_consecutive_losses=max_streak,
    )


def _max_consecutive_losses(trades: list[Trade]) -> int:
    best = 0
    current = 0
    for t in trades:
        if (t.pnl or 0) <= 0:
            current += 1
            if current > best:
                best = current
        else:
            current = 0
    return best
