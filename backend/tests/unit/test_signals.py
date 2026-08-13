"""Tests for signal engine (MTF gate, R:R, confidence, propagation).

We synthesize AnalysisResult objects directly so we're testing the engine's
combining logic — not the full indicator/analysis pipeline (that's covered
in test_analysis.py).
"""
from datetime import UTC, datetime

import pytest

from app.services.analysis.types import (
    AnalysisResult,
    Direction,
    MomentumAnalysis,
    StructureAnalysis,
    SupportResistanceAnalysis,
    TrendAnalysis,
    VolatilityAnalysis,
)
from app.services.signals import (
    RiskReward,
    SignalDirection,
    compute_risk_reward,
    generate_signal,
)


def _mk_analysis(
    direction: Direction,
    *,
    price: float = 4400.0,
    score: float = 60.0,
    atr: float = 5.0,
    warnings: list[str] | None = None,
) -> AnalysisResult:
    """Build a minimal AnalysisResult for engine testing.

    We don't need real indicator values — the engine only reads
    `direction`, `score`, `price`, `volatility.atr`, `reasons`, and `warnings`.
    """
    return AnalysisResult(
        direction=direction,
        score=score,
        price=price,
        trend=TrendAnalysis(
            direction=direction, score=score * 0.28, ema20=price, ema50=price, ema200=price,
            price=price, reasons=["trend reason"],
        ),
        momentum=MomentumAnalysis(
            direction=direction, score=score * 0.22, rsi=60.0, macd=0.5,
            macd_signal=0.3, macd_histogram=0.2, reasons=["momentum reason"],
        ),
        volatility=VolatilityAnalysis(
            score=score * 0.11, atr=atr, atr_pct=(atr / price) * 100, level="NORMAL",
            reasons=["volatility reason"],
        ),
        structure=StructureAnalysis(
            direction=direction, score=score * 0.22, swing_highs=[], swing_lows=[],
            bos=False, choch=False, reasons=["structure reason"],
        ),
        support_resistance=SupportResistanceAnalysis(
            score=score * 0.17, nearest_support=price - 20, nearest_resistance=price + 20,
            distance_to_support_atr=4.0, distance_to_resistance_atr=4.0,
            reasons=["sr reason"],
        ),
        reasons=["trend reason", "momentum reason", "structure reason", "sr reason", "volatility reason"],
        warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# Risk-reward
# ---------------------------------------------------------------------------


def test_rr_buy_computes_correct_targets() -> None:
    rr = compute_risk_reward(SignalDirection.BUY, price=4400.0, atr=5.0)
    assert rr.entry == 4400.0
    assert rr.stop_loss == pytest.approx(4400.0 - 7.5)   # 1.5 × 5
    assert rr.take_profit_1 == pytest.approx(4400.0 + 15.0)  # 3.0 × 5
    assert rr.take_profit_2 == pytest.approx(4400.0 + 22.5)  # 4.5 × 5
    assert rr.risk_reward == pytest.approx(2.0)  # 15/7.5


def test_rr_sell_mirrors_directions() -> None:
    rr = compute_risk_reward(SignalDirection.SELL, price=4400.0, atr=5.0)
    assert rr.stop_loss == pytest.approx(4400.0 + 7.5)
    assert rr.take_profit_1 == pytest.approx(4400.0 - 15.0)
    assert rr.risk_reward == pytest.approx(2.0)


def test_rr_score_scales_with_ratio() -> None:
    # R:R = 2.0 (default 3:1.5 mults) should give a mid-to-high score.
    rr = compute_risk_reward(SignalDirection.BUY, price=100.0, atr=1.0)
    assert 5.0 < rr.score < 10.0

    # R:R = 3.0 (custom) should max out at 10.
    rr = compute_risk_reward(SignalDirection.BUY, price=100.0, atr=1.0, tp1_mult=4.5)
    assert rr.score == pytest.approx(10.0)


def test_rr_zero_atr_gives_zero_score() -> None:
    rr = compute_risk_reward(SignalDirection.BUY, price=100.0, atr=0.0)
    assert rr.score == 0.0
    assert rr.risk_reward == 0.0


def test_rr_wait_direction_raises() -> None:
    with pytest.raises(ValueError):
        compute_risk_reward(SignalDirection.WAIT, price=100.0, atr=1.0)


# ---------------------------------------------------------------------------
# MTF gate — WAIT cases
# ---------------------------------------------------------------------------


def test_wait_when_4h_neutral() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.NEUTRAL),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.WAIT
    assert result.entry is None
    assert result.confidence == 0.0
    assert any("4H trend is NEUTRAL" in r for r in result.reasons)


def test_wait_when_4h_and_1h_disagree() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.BEARISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.WAIT
    assert any("1H (BEARISH) disagrees" in r for r in result.reasons)


def test_wait_when_15m_disagrees_with_4h() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BEARISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.WAIT


def test_wait_when_missing_required_timeframe() -> None:
    # 15m missing → WAIT
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.WAIT
    assert any("Missing analysis" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# BUY / SELL firing
# ---------------------------------------------------------------------------


def test_buy_signal_fires_on_full_bullish_agreement() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH, score=70.0),
        "1h": _mk_analysis(Direction.BULLISH, score=65.0),
        "15m": _mk_analysis(Direction.BULLISH, score=60.0, price=4400.0, atr=5.0),
        "5m": _mk_analysis(Direction.BULLISH, score=55.0),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.BUY
    assert result.entry == 4400.0
    assert result.stop_loss < result.entry
    assert result.take_profit_1 > result.entry
    assert 50.0 < result.confidence <= 100.0
    # Reason list contains per-TF breakdowns.
    assert any("[4h]" in r for r in result.reasons)
    assert any("[15m]" in r for r in result.reasons)


def test_sell_signal_fires_on_full_bearish_agreement() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BEARISH, score=70.0),
        "1h": _mk_analysis(Direction.BEARISH, score=65.0),
        "15m": _mk_analysis(Direction.BEARISH, score=60.0, price=4400.0, atr=5.0),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.SELL
    assert result.stop_loss > result.entry
    assert result.take_profit_1 < result.entry


def test_1h_neutral_passes_when_4h_and_15m_bullish() -> None:
    # 1H NEUTRAL is allowed — only DISAGREEMENT triggers WAIT.
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.NEUTRAL),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.direction == SignalDirection.BUY


def test_confidence_bounded_0_to_100() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH, score=90.0),  # max
        "1h": _mk_analysis(Direction.BULLISH, score=90.0),
        "15m": _mk_analysis(Direction.BULLISH, score=90.0, atr=5.0),
        "5m": _mk_analysis(Direction.BULLISH, score=90.0),
    }
    result = generate_signal("XAUUSD", analyses)
    assert result.confidence <= 100.0


def test_warnings_propagate_to_signal() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH, warnings=["Extreme volatility"]),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses)
    assert "Extreme volatility" in result.warnings


def test_breakdown_includes_per_tf_scores() -> None:
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH, score=70.0),
        "1h": _mk_analysis(Direction.BULLISH, score=60.0),
        "15m": _mk_analysis(Direction.BULLISH, score=50.0),
    }
    result = generate_signal("XAUUSD", analyses)
    assert "score_4h" in result.breakdown
    assert "score_1h" in result.breakdown
    assert "score_15m" in result.breakdown
    assert "risk_reward" in result.breakdown
    assert "analysis_blended" in result.breakdown


def test_generated_at_stored() -> None:
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    analyses = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    result = generate_signal("XAUUSD", analyses, now=now)
    assert result.generated_at == now


def test_is_actionable_property() -> None:
    analyses_buy = {
        "4h": _mk_analysis(Direction.BULLISH),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    analyses_wait = {
        "4h": _mk_analysis(Direction.NEUTRAL),
        "1h": _mk_analysis(Direction.BULLISH),
        "15m": _mk_analysis(Direction.BULLISH),
    }
    assert generate_signal("XAUUSD", analyses_buy).is_actionable is True
    assert generate_signal("XAUUSD", analyses_wait).is_actionable is False
