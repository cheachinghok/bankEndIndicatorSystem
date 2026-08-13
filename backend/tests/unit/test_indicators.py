"""Reference-value tests for the indicator library.

We use hand-verifiable inputs (constant series, monotonic series, small
hand-computed examples) rather than snapshot testing so any regression is
immediately readable.
"""
import math

import pytest

from app.services.indicators import (
    IncrementalEMA,
    atr,
    atr_latest,
    ema,
    ema_latest,
    macd,
    macd_latest,
    rsi,
    rsi_latest,
)
from app.services.indicators.candles import closes, highs, lows
from app.services.market_data.models import Candle
from datetime import UTC, datetime, timedelta


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


def test_ema_constant_series_stays_flat() -> None:
    values = [100.0] * 20
    result = ema(values, length=5)
    # first 4 values are warmup NaN
    for v in result[:4]:
        assert math.isnan(v)
    # from index 4 onwards, everything equals 100
    for v in result[4:]:
        assert v == pytest.approx(100.0)


def test_ema_seeded_at_length_minus_one_is_sma() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = ema(values, length=5)
    assert result[-1] == pytest.approx(3.0)  # SMA(1..5) = 3


def test_ema_matches_hand_computed_next_step() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 10.0]
    # SMA seed = 3.0, alpha = 2/6 = 0.3333...
    # EMA[5] = 0.3333*10 + 0.6667*3 = 3.333 + 2.000 = 5.333...
    result = ema(values, length=5)
    assert result[-1] == pytest.approx(3.0 + (10.0 - 3.0) * (2.0 / 6.0))


def test_ema_too_few_values_all_nan() -> None:
    result = ema([1.0, 2.0], length=5)
    assert all(math.isnan(v) for v in result)


def test_ema_latest_returns_last() -> None:
    assert ema_latest([100.0] * 10, length=3) == pytest.approx(100.0)


def test_incremental_ema_matches_batch() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    batch = ema(values, length=5)

    # Seed the incremental with the first 5 values, then push the rest.
    inc = IncrementalEMA.from_series(values[:5], length=5)
    assert inc.value == pytest.approx(batch[4])
    for i in range(5, 10):
        inc.push(values[i])
        assert inc.value == pytest.approx(batch[i])


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


def test_rsi_pure_uptrend_is_100() -> None:
    values = [float(x) for x in range(1, 30)]  # strictly increasing
    result = rsi(values, length=14)
    assert result[-1] == pytest.approx(100.0)


def test_rsi_pure_downtrend_is_zero() -> None:
    values = [float(x) for x in range(30, 0, -1)]  # strictly decreasing
    result = rsi(values, length=14)
    assert result[-1] == pytest.approx(0.0)


def test_rsi_flat_series_is_50_by_convention() -> None:
    values = [100.0] * 20
    result = rsi(values, length=14)
    assert result[-1] == pytest.approx(50.0)


def test_rsi_warmup_period_is_nan() -> None:
    values = [float(x) for x in range(1, 30)]
    result = rsi(values, length=14)
    # Need 15 closes (14 deltas) to seed: first RSI value is at index `length` = 14.
    # So indices 0..13 (14 values) are NaN; index 14 is the first real RSI.
    for v in result[:14]:
        assert math.isnan(v)
    assert not math.isnan(result[14])


def test_rsi_too_few_values_all_nan() -> None:
    result = rsi([1.0, 2.0, 3.0], length=14)
    assert all(math.isnan(v) for v in result)


def test_rsi_latest_returns_last() -> None:
    values = [float(x) for x in range(1, 30)]
    assert rsi_latest(values, length=14) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


def test_macd_constant_series_is_zero() -> None:
    values = [100.0] * 60
    result = macd(values)
    # Once both EMAs are seeded, macd_line = 0, signal = 0, histogram = 0.
    assert result.macd[-1] == pytest.approx(0.0)
    assert result.signal[-1] == pytest.approx(0.0)
    assert result.histogram[-1] == pytest.approx(0.0)


def test_macd_uptrend_produces_positive_line() -> None:
    values = [float(x) for x in range(1, 100)]
    result = macd(values)
    # Uptrend → fast EMA > slow EMA → macd line > 0.
    assert result.macd[-1] > 0
    # After enough samples the histogram should stabilize near zero (both
    # EMAs are catching up), but sign should still be positive on trending data.


def test_macd_downtrend_produces_negative_line() -> None:
    values = [float(x) for x in range(100, 1, -1)]
    result = macd(values)
    assert result.macd[-1] < 0


def test_macd_rejects_invalid_periods() -> None:
    with pytest.raises(ValueError, match="fast .* < slow"):
        macd([1.0] * 30, fast=26, slow=12)


def test_macd_latest_tuple_shape() -> None:
    values = [100.0] * 60
    m, s, h = macd_latest(values)
    assert m == pytest.approx(0.0) and s == pytest.approx(0.0) and h == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


def test_atr_zero_range_series() -> None:
    # H=L=C for every candle → TR = 0 → ATR = 0.
    h = [100.0] * 20
    l = [100.0] * 20
    c = [100.0] * 20
    result = atr(h, l, c, length=14)
    assert result[-1] == pytest.approx(0.0)


def test_atr_constant_hlc_range_equals_range() -> None:
    # Every candle has H-L=10 and no gaps → TR always 10 → ATR = 10.
    h = [110.0] * 20
    l = [100.0] * 20
    c = [105.0] * 20
    result = atr(h, l, c, length=14)
    assert result[-1] == pytest.approx(10.0)


def test_atr_warmup_is_nan() -> None:
    h = [110.0] * 20
    l = [100.0] * 20
    c = [105.0] * 20
    result = atr(h, l, c, length=14)
    for v in result[:14]:
        assert math.isnan(v)
    assert not math.isnan(result[14])


def test_atr_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        atr([1.0, 2.0], [1.0], [1.0, 2.0])


def test_atr_latest_returns_last() -> None:
    h = [110.0] * 20
    l = [100.0] * 20
    c = [105.0] * 20
    assert atr_latest(h, l, c, length=14) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Candle extractors
# ---------------------------------------------------------------------------


def _make_candles(n: int) -> list[Candle]:
    base = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)
    return [
        Candle(
            timestamp=base + timedelta(minutes=15 * i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
        )
        for i in range(n)
    ]


def test_candle_extractors_shape() -> None:
    cs = _make_candles(5)
    assert closes(cs) == [100.5, 101.5, 102.5, 103.5, 104.5]
    assert highs(cs) == [101.0, 102.0, 103.0, 104.0, 105.0]
    assert lows(cs) == [99.0, 100.0, 101.0, 102.0, 103.0]


def test_integration_pipeline_with_candles() -> None:
    """Smoke test: pull closes/highs/lows off Candles, run every indicator."""
    cs = _make_candles(50)
    close_s = closes(cs)
    high_s = highs(cs)
    low_s = lows(cs)

    ema20 = ema_latest(close_s, length=20)
    r = rsi_latest(close_s, length=14)
    m, s, h = macd_latest(close_s)
    a = atr_latest(high_s, low_s, close_s, length=14)

    # Uptrend → EMA > 100, RSI = 100, MACD line > 0, ATR = 2 (H-L on every candle).
    assert ema20 > 100
    assert r == pytest.approx(100.0)
    assert m > 0
    assert a == pytest.approx(2.0)
