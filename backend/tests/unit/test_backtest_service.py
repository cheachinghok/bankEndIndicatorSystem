"""Tests for the backtest orchestration service (serialization).

REST-level integration tests require a live DB + candles; covered manually
via the curl examples in the README. Here we test the pure serialization
transform so it can't silently regress.
"""
from datetime import UTC, datetime

from app.backtesting import BacktestConfig
from app.backtesting.stats import compute_stats
from app.backtesting.types import BacktestResult, ExitReason, Trade
from app.services.backtesting.service import serialize_result
from app.services.signals.types import SignalDirection


def _trade(direction: SignalDirection, pnl: float) -> Trade:
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    return Trade(
        symbol="XAUUSD",
        direction=direction,
        entry_time=now, entry_price=4400.0, stop_loss=4395.0, take_profit=4410.0,
        position_size=1.0, signal_confidence=80.0,
        exit_time=now, exit_price=4400.0 + pnl,
        exit_reason=ExitReason.TP1 if pnl > 0 else ExitReason.SL,
        pnl=pnl, pnl_r=pnl / 5.0,
        equity_before=10_000.0, equity_after=10_000.0 + pnl,
    )


def test_serialize_result_is_json_safe() -> None:
    import json

    trades = [_trade(SignalDirection.BUY, 100.0), _trade(SignalDirection.SELL, -50.0)]
    stats = compute_stats(trades, 10_000.0, 10_050.0, 0.0, 10_100.0)
    result = BacktestResult(
        symbol="XAUUSD",
        config=BacktestConfig(),
        trades=trades,
        equity_curve=[(datetime(2026, 8, 13, 12, 0, tzinfo=UTC), 10_050.0)],
        final_equity=10_050.0,
        stats=stats,
    )

    payload = serialize_result(result)
    # Must round-trip through json.dumps without any custom encoders.
    encoded = json.dumps(payload)
    assert '"XAUUSD"' in encoded or '"symbol"' not in payload["config"]  # config has no symbol
    # Enum values serialized as strings.
    assert payload["trades"][0]["direction"] == "BUY"
    assert payload["trades"][0]["exit_reason"] == "TP1"
    assert payload["trades"][1]["direction"] == "SELL"
    # Datetimes serialized as ISO strings.
    assert isinstance(payload["trades"][0]["entry_time"], str)
    assert payload["trades"][0]["entry_time"].endswith("+00:00")
    assert isinstance(payload["equity_curve"][0][0], str)


def test_serialize_result_open_trade_has_none_exit() -> None:
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    open_trade = Trade(
        symbol="XAUUSD",
        direction=SignalDirection.BUY,
        entry_time=now, entry_price=4400.0, stop_loss=4395.0, take_profit=4410.0,
        position_size=1.0, signal_confidence=80.0,
        exit_time=None, exit_price=None, exit_reason=None,
        pnl=None, pnl_r=None, equity_before=10_000.0, equity_after=None,
    )
    result = BacktestResult(
        symbol="XAUUSD",
        config=BacktestConfig(),
        trades=[open_trade],
        equity_curve=[],
        final_equity=10_000.0,
        stats=compute_stats([], 10_000.0, 10_000.0, 0.0, 10_000.0),
    )
    payload = serialize_result(result)
    assert payload["trades"][0]["exit_time"] is None
    assert payload["trades"][0]["exit_reason"] is None
