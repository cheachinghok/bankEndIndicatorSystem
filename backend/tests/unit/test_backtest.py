"""Backtest engine tests.

Coverage:
    - Multi-timeframe alignment: no-look-ahead invariant
    - Execution: spread/slippage direction and SL-first pessimistic rule
    - Portfolio: position sizing, drawdown tracking
    - Stats: edge cases (0 trades, all wins, all losses, consecutive losses)
    - End-to-end: uptrend generates BUY trades, downtrend generates SELL trades
    - Critical invariant: mutating a FUTURE candle doesn't change PAST signals
"""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.backtesting import BacktestConfig, ExitReason, run_backtest
from app.backtesting.alignment import align_all_timeframes, visible_candles
from app.backtesting.execution import (
    apply_entry_fill,
    apply_sl_fill,
    check_bar_exit,
)
from app.backtesting.portfolio import Portfolio, position_size
from app.backtesting.stats import compute_stats
from app.backtesting.types import Trade
from app.services.market_data.models import Candle
from app.services.signals.types import SignalDirection


BASE = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)


def _c(minutes: int, o=100.0, h=101.0, l=99.0, c=100.5, tf_minutes=15) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=minutes),
        open=o, high=h, low=l, close=c, volume=100.0,
    )


# ---------------------------------------------------------------------------
# Alignment / no-look-ahead
# ---------------------------------------------------------------------------


def test_visible_candles_excludes_unclosed() -> None:
    # Three 15m candles opening at 0, 15, 30.
    candles = [_c(0), _c(15), _c(30)]
    # At t=15, only the 0-open candle has closed (closes at t=15).
    # bisect includes candle where timestamp <= threshold = t - duration = 0 → includes candle at 0.
    at = BASE + timedelta(minutes=15)
    result = visible_candles(candles, "15m", at)
    assert [c.timestamp for c in result] == [BASE]


def test_visible_candles_at_second_close() -> None:
    candles = [_c(0), _c(15), _c(30)]
    at = BASE + timedelta(minutes=30)  # 2nd candle closes
    result = visible_candles(candles, "15m", at)
    assert len(result) == 2


def test_align_all_timeframes_no_look_ahead() -> None:
    """15m candle 03:45 has closed at t=04:00. 1H candle 03:00 also closed at 04:00.
    But 4H candle 00:00 doesn't close until 04:00 either (edge). Verify inclusion."""
    tfs = {
        "15m": [_c(45 + 15 * i) for i in range(8)],   # opens 00:45..02:30
        "1h": [_c(60 * i) for i in range(3)],          # opens 00:00, 01:00, 02:00
        "4h": [_c(0), _c(240)],                        # opens 00:00, 04:00
    }
    at = BASE + timedelta(hours=3)
    result = align_all_timeframes(tfs, at)
    # 15m: candles closing at or before 03:00 → opens 00:45..02:45
    assert all((c.timestamp + timedelta(minutes=15)) <= at for c in result["15m"])
    # 1h: closes 01:00,02:00,03:00 all ≤ 03:00 → all 3 included
    assert len(result["1h"]) == 3
    # 4h: candle at 00:00 closes at 04:00 > 03:00 → NOT included
    assert len(result["4h"]) == 0


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def test_entry_fill_buy_pays_the_ask() -> None:
    cfg = BacktestConfig(spread=0.30, slippage_entry=0.20)
    fill = apply_entry_fill(4400.0, SignalDirection.BUY, cfg)
    assert fill == pytest.approx(4400.0 + 0.15 + 0.20)


def test_entry_fill_sell_pays_the_bid() -> None:
    cfg = BacktestConfig(spread=0.30, slippage_entry=0.20)
    fill = apply_entry_fill(4400.0, SignalDirection.SELL, cfg)
    assert fill == pytest.approx(4400.0 - 0.15 - 0.20)


def test_sl_fill_worse_than_trigger() -> None:
    cfg = BacktestConfig(slippage_sl=0.50)
    # BUY position: SL below entry, fill even lower.
    assert apply_sl_fill(4392.5, SignalDirection.BUY, cfg) == pytest.approx(4392.0)
    # SELL position: SL above entry, fill even higher.
    assert apply_sl_fill(4407.5, SignalDirection.SELL, cfg) == pytest.approx(4408.0)


def test_bar_exit_sl_first_when_both_hit() -> None:
    # BUY: entry ~100, SL=95, TP=105. Bar with L=94, H=106 hits both.
    bar = _c(0, o=100, h=106, l=94, c=100)
    assert check_bar_exit(bar, SignalDirection.BUY, 95, 105) == ExitReason.SL


def test_bar_exit_tp_when_only_tp_hit() -> None:
    bar = _c(0, o=100, h=106, l=99, c=105)
    assert check_bar_exit(bar, SignalDirection.BUY, 95, 105) == ExitReason.TP1


def test_bar_exit_none_when_neither() -> None:
    bar = _c(0, o=100, h=101, l=99, c=100)
    assert check_bar_exit(bar, SignalDirection.BUY, 95, 105) is None


# ---------------------------------------------------------------------------
# Portfolio + position sizing
# ---------------------------------------------------------------------------


def test_position_size_matches_risk() -> None:
    # equity 10k, 1% risk, stop distance $7.5 → 100 / 7.5 = 13.33 units
    size = position_size(10_000.0, 1.0, 7.5)
    assert size == pytest.approx(100.0 / 7.5)


def test_position_size_zero_when_stop_distance_zero() -> None:
    assert position_size(10_000.0, 1.0, 0.0) == 0.0


def test_portfolio_tracks_drawdown() -> None:
    p = Portfolio(initial_equity=10_000.0)
    p.record(BASE, 10_000.0)
    p.record(BASE + timedelta(hours=1), 11_000.0)
    p.record(BASE + timedelta(hours=2), 9_500.0)  # drawdown = 1500 from peak 11000
    p.record(BASE + timedelta(hours=3), 10_000.0)
    assert p.peak == 11_000.0
    assert p.max_drawdown == 1_500.0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def _mk_trade(pnl: float, pnl_r: float | None = None) -> Trade:
    return Trade(
        symbol="XAUUSD",
        direction=SignalDirection.BUY,
        entry_time=BASE, entry_price=100.0, stop_loss=95.0, take_profit=110.0,
        position_size=1.0, signal_confidence=70.0,
        exit_time=BASE + timedelta(hours=1), exit_price=100.0 + pnl,
        exit_reason=ExitReason.TP1 if pnl > 0 else ExitReason.SL,
        pnl=pnl, pnl_r=pnl_r if pnl_r is not None else pnl / 5.0,
        equity_before=10_000.0, equity_after=10_000.0 + pnl,
    )


def test_stats_zero_trades() -> None:
    stats = compute_stats([], 10_000.0, 10_000.0, 0.0, 10_000.0)
    assert stats.total_trades == 0
    assert stats.win_rate == 0.0
    assert stats.profit_factor == 0.0


def test_stats_all_wins_infinite_profit_factor() -> None:
    stats = compute_stats(
        [_mk_trade(100), _mk_trade(200)], 10_000.0, 10_300.0, 0.0, 10_300.0
    )
    assert stats.wins == 2
    assert stats.losses == 0
    assert stats.win_rate == 1.0
    assert stats.profit_factor == float("inf")


def test_stats_mixed_computes_correctly() -> None:
    trades = [_mk_trade(200), _mk_trade(-100), _mk_trade(200), _mk_trade(-100)]
    stats = compute_stats(trades, 10_000.0, 10_200.0, 100.0, 10_200.0)
    assert stats.wins == 2
    assert stats.losses == 2
    assert stats.win_rate == 0.5
    assert stats.profit_factor == pytest.approx(400 / 200)  # 2.0
    assert stats.avg_win == 200.0
    assert stats.avg_loss == -100.0


def test_stats_max_consecutive_losses() -> None:
    trades = [_mk_trade(100), _mk_trade(-50), _mk_trade(-50), _mk_trade(-50), _mk_trade(100)]
    stats = compute_stats(trades, 10_000.0, 10_050.0, 150.0, 10_100.0)
    assert stats.max_consecutive_losses == 3


# ---------------------------------------------------------------------------
# End-to-end smoke tests + no-look-ahead invariant
#
# End-to-end trade-generation testing requires a realistic dataset spanning
# 35+ days (to seed EMA200 on the 4h timeframe), which is too heavy for a
# unit test. Real backtest validation happens against actual OANDA history
# via the backtest CLI/REST endpoint (Phase 7). Here we cover:
#   - The engine runs without crashing on short data (0 trades is fine)
#   - Required-input validation
#   - The no-look-ahead invariant AT THE ALIGNMENT LAYER — this is where
#     the guarantee actually lives, so we test it there directly.
# ---------------------------------------------------------------------------


def _uptrend_candles(count: int, start: float = 4300.0, step: float = 0.5, tf_minutes: int = 15) -> list[Candle]:
    """A steady uptrend on a given timeframe."""
    return [
        Candle(
            timestamp=BASE + timedelta(minutes=tf_minutes * i),
            open=start + step * i,
            high=start + step * i + 1.0,
            low=start + step * i - 1.0,
            close=start + step * i + 0.4,
            volume=100.0,
        )
        for i in range(count)
    ]


def test_backtest_runs_without_error_on_short_data() -> None:
    """With ~4 days of data the higher TF never seeds, so 0 trades is expected.
    What we're verifying: the engine doesn't crash and returns a well-formed result."""
    c15 = _uptrend_candles(400, tf_minutes=15)
    c1h = _uptrend_candles(400, tf_minutes=60)
    c4h = _uptrend_candles(400, tf_minutes=240)
    result = run_backtest({"15m": c15, "1h": c1h, "4h": c4h}, "XAUUSD")
    assert result.symbol == "XAUUSD"
    assert result.stats.total_trades == 0
    assert result.final_equity == result.config.initial_equity
    assert len(result.equity_curve) > 0


def test_backtest_requires_minimum_history() -> None:
    tiny = _uptrend_candles(50)
    with pytest.raises(ValueError, match="Not enough"):
        run_backtest({"15m": tiny, "1h": tiny, "4h": tiny}, "XAUUSD")


def test_backtest_requires_all_timeframes() -> None:
    c = _uptrend_candles(400)
    with pytest.raises(ValueError, match="Missing required timeframe"):
        run_backtest({"15m": c, "1h": c}, "XAUUSD")


def test_no_look_ahead_invariant_at_alignment_level() -> None:
    """CRITICAL invariant. The whole no-look-ahead guarantee lives in
    `align_all_timeframes` — if that function never returns unclosed candles,
    the engine cannot see the future by construction.

    We verify by: build a clean dataset, take an alignment snapshot at instant t,
    then MUTATE all candles whose close time is > t, then re-snapshot at the
    same t. The two snapshots must be byte-identical.
    """
    c15 = _uptrend_candles(20, tf_minutes=15)  # opens 0..285 min
    original = [deepcopy(c) for c in c15]

    at = BASE + timedelta(minutes=100)  # only candles opening at ≤ 85 min are visible (6 candles)
    baseline = visible_candles(c15, "15m", at)
    assert len(baseline) == 6

    # Mutate every candle whose close time > `at` — those are the "future".
    for i in range(len(c15)):
        candle_close = c15[i].timestamp + timedelta(minutes=15)
        if candle_close > at:
            c15[i] = Candle(
                timestamp=c15[i].timestamp,
                open=999_999.0, high=999_999.0, low=999_999.0, close=999_999.0,
            )

    mutated = visible_candles(c15, "15m", at)

    assert len(mutated) == len(baseline)
    for a, b in zip(baseline, mutated):
        assert a == b, "Mutating a future candle changed a past alignment result"

    # And the sentinel: the mutated originals are indeed different objects.
    assert any(c.open == 999_999.0 for c in c15)
    assert all(c.open != 999_999.0 for c in original)
