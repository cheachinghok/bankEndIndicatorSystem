"""Tests for the signal worker serializer.

The full integration (Redis pubsub + DB + async worker loop) is exercised
end-to-end via manual verification in the README. Here we test the pure
serialization function so it can't silently regress.
"""
import json
from datetime import UTC, datetime

from app.services.signals import SignalDirection, SignalResult
from app.workers.signal_worker import _serialize_signal


def _mk_signal(direction: SignalDirection, confidence: float) -> SignalResult:
    return SignalResult(
        symbol="XAUUSD",
        direction=direction,
        confidence=confidence,
        timeframe="15m",
        entry=4400.0 if direction != SignalDirection.WAIT else None,
        stop_loss=4392.5 if direction != SignalDirection.WAIT else None,
        take_profit_1=4415.0 if direction != SignalDirection.WAIT else None,
        take_profit_2=4422.5 if direction != SignalDirection.WAIT else None,
        risk_reward=2.0 if direction != SignalDirection.WAIT else None,
        breakdown={"analysis_blended": 65.0, "risk_reward": 8.0},
        reasons=["4H+1H+15M aligned BULLISH", "R:R = 1:2.00 (score 8.0/10)"],
        warnings=[],
        generated_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
    )


def test_serialize_buy_signal_shape() -> None:
    result = _mk_signal(SignalDirection.BUY, confidence=82.0)
    payload = json.loads(_serialize_signal(result, "XAUUSD"))

    assert payload["symbol"] == "XAUUSD"
    assert payload["direction"] == "BUY"
    assert payload["confidence"] == 82.0
    assert payload["entry"] == 4400.0
    assert payload["stop_loss"] == 4392.5
    assert payload["take_profit_1"] == 4415.0
    assert payload["risk_reward"] == 2.0
    assert payload["timeframe"] == "15m"
    assert payload["generated_at"] == "2026-08-13T12:00:00Z"
    assert isinstance(payload["reasons"], list) and len(payload["reasons"]) == 2
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["breakdown"], dict)


def test_serialize_wait_signal_has_null_prices() -> None:
    result = _mk_signal(SignalDirection.WAIT, confidence=0.0)
    payload = json.loads(_serialize_signal(result, "XAUUSD"))
    assert payload["direction"] == "WAIT"
    assert payload["entry"] is None
    assert payload["stop_loss"] is None
    assert payload["risk_reward"] is None


def test_serialize_generated_at_fallback_to_now() -> None:
    # If SignalResult somehow has no generated_at, serializer should use now().
    result = SignalResult(
        symbol="XAUUSD",
        direction=SignalDirection.BUY,
        confidence=70.0,
        timeframe="15m",
        entry=4400.0, stop_loss=4392.5, take_profit_1=4415.0,
        take_profit_2=4422.5, risk_reward=2.0,
        generated_at=None,
    )
    payload = json.loads(_serialize_signal(result, "XAUUSD"))
    # Just check it's a well-formed ISO-Z string.
    assert payload["generated_at"].endswith("Z")
    assert "T" in payload["generated_at"]
