"""Tests for the market analysis engine.

Uses synthetic candle series (uptrend, downtrend, choppy, quiet) to verify
each bucket returns the expected direction and reasonable scores. We avoid
snapshot testing so any change in scoring logic must be justified by
updating a specific numeric expectation.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.services.analysis import Direction, analyze
from app.services.analysis.momentum import analyze_momentum
from app.services.analysis.structure import analyze_structure
from app.services.analysis.trend import analyze_trend
from app.services.analysis.volatility import analyze_volatility
from app.services.market_data.models import Candle


BASE_TIME = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)


def _mk(closes: list[float], *, spread: float = 1.0) -> list[Candle]:
    """Build candles from a close series with a small H/L spread."""
    return [
        Candle(
            timestamp=BASE_TIME + timedelta(minutes=15 * i),
            open=c,
            high=c + spread,
            low=c - spread,
            close=c,
            volume=100.0,
        )
        for i, c in enumerate(closes)
    ]


def _uptrend(n: int = 250, start: float = 100.0, step: float = 0.5) -> list[Candle]:
    return _mk([start + step * i for i in range(n)])


def _downtrend(n: int = 250, start: float = 200.0, step: float = 0.5) -> list[Candle]:
    return _mk([start - step * i for i in range(n)])


def _flat(n: int = 250, price: float = 100.0) -> list[Candle]:
    return _mk([price] * n)


def _choppy(n: int = 250, base: float = 100.0, amplitude: float = 2.0) -> list[Candle]:
    return _mk([base + (amplitude if i % 2 == 0 else -amplitude) for i in range(n)])


# ---------------------------------------------------------------------------
# Bucket-level tests
# ---------------------------------------------------------------------------


def test_trend_uptrend_is_bullish() -> None:
    r = analyze_trend([c.close for c in _uptrend()])
    assert r.direction == Direction.BULLISH
    assert r.score >= 15


def test_trend_downtrend_is_bearish() -> None:
    r = analyze_trend([c.close for c in _downtrend()])
    assert r.direction == Direction.BEARISH
    assert r.score >= 15


def test_trend_flat_is_neutral() -> None:
    r = analyze_trend([c.close for c in _flat()])
    assert r.direction == Direction.NEUTRAL


def test_trend_insufficient_history_neutral_zero() -> None:
    r = analyze_trend([100.0] * 50)
    assert r.direction == Direction.NEUTRAL
    assert r.score == 0.0


def test_momentum_uptrend_is_bullish() -> None:
    r = analyze_momentum([c.close for c in _uptrend()])
    assert r.direction == Direction.BULLISH
    assert r.score > 0


def test_momentum_downtrend_is_bearish() -> None:
    r = analyze_momentum([c.close for c in _downtrend()])
    assert r.direction == Direction.BEARISH


def test_volatility_flat_is_low() -> None:
    candles = _mk([100.0] * 30, spread=0.0)
    r = analyze_volatility([c.high for c in candles], [c.low for c in candles], [c.close for c in candles])
    assert r.level in ("LOW", "NORMAL")  # zero ATR reads as LOW


def test_volatility_bucketing() -> None:
    # ATR of exactly 0.5 on price 100 → 0.5% → NORMAL
    candles = _mk([100.0] * 30, spread=0.25)  # H-L = 0.5
    r = analyze_volatility([c.high for c in candles], [c.low for c in candles], [c.close for c in candles])
    assert r.level == "NORMAL"
    assert r.score == 10.0


def test_structure_uptrend_detects_higher_highs() -> None:
    # Synthetic zig-zag with rising peaks and troughs.
    closes = []
    for i in range(40):
        base = 100 + i
        closes.extend([base, base + 2, base + 1, base + 3, base])
    r = analyze_structure(
        [c + 1 for c in closes], [c - 1 for c in closes], closes
    )
    assert r.direction == Direction.BULLISH


# ---------------------------------------------------------------------------
# Full-engine tests
# ---------------------------------------------------------------------------


def test_analyze_uptrend_full_result() -> None:
    r = analyze(_uptrend())
    assert r.direction == Direction.BULLISH
    assert r.score > 30  # multiple buckets contributing
    assert r.trend.direction == Direction.BULLISH
    assert r.momentum.direction == Direction.BULLISH
    # Reasons list is non-empty and readable.
    assert any("EMA" in reason for reason in r.reasons)
    assert any("RSI" in reason for reason in r.reasons)


def test_analyze_downtrend_full_result() -> None:
    r = analyze(_downtrend())
    assert r.direction == Direction.BEARISH
    assert r.trend.direction == Direction.BEARISH
    assert r.momentum.direction == Direction.BEARISH


def test_analyze_flat_is_neutral() -> None:
    r = analyze(_flat())
    assert r.direction == Direction.NEUTRAL
    # Neutral means no directional score should be very high.
    assert r.trend.score == 0.0
    # Volatility is still measured even if no trend.
    assert r.volatility.score > 0


def test_analyze_insufficient_history_neutral() -> None:
    # 15 candles is below every bucket's MIN_HISTORY (volatility 20, structure 30,
    # momentum 40, S/R 40, trend 210) → nothing can opine → NEUTRAL.
    r = analyze(_uptrend(n=15))
    assert r.direction == Direction.NEUTRAL
    assert r.trend.score == 0.0
    assert r.momentum.score == 0.0
    assert r.structure.score == 0.0
    assert r.volatility.score == 0.0


def test_analyze_score_bounded_by_max() -> None:
    r = analyze(_uptrend(n=400))
    # ANALYSIS_MAX = 90. Should never exceed even on ideal uptrend.
    assert r.score <= 90


def test_analyze_extreme_volatility_flags_warning() -> None:
    # Alternating +/- 5% swings on price 100 → ATR ~10 → 10% → EXTREME
    closes = [100.0 + (10.0 if i % 2 == 0 else -10.0) for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    candles = [
        Candle(
            timestamp=BASE_TIME + timedelta(minutes=15 * i),
            open=closes[i],
            high=highs[i],
            low=lows[i],
            close=closes[i],
        )
        for i in range(60)
    ]
    r = analyze(candles)
    assert r.volatility.level == "EXTREME"
    assert any("Extreme volatility" in w for w in r.warnings)


def test_analysis_result_matches_bucket_max_ceilings() -> None:
    """No bucket can exceed its declared max even on ideal inputs."""
    r = analyze(_uptrend(n=400))
    from app.services.analysis.types import (
        MOMENTUM_MAX,
        STRUCTURE_MAX,
        SUPPORT_RESISTANCE_MAX,
        TREND_MAX,
        VOLATILITY_MAX,
    )
    assert r.trend.score <= TREND_MAX
    assert r.momentum.score <= MOMENTUM_MAX
    assert r.structure.score <= STRUCTURE_MAX
    assert r.support_resistance.score <= SUPPORT_RESISTANCE_MAX
    assert r.volatility.score <= VOLATILITY_MAX
