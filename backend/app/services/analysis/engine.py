"""Analysis engine — compose all bucket analyzers.

The engine runs each bucket independently, then:
1. Determines an aggregate direction by majority vote among directional buckets
   (trend, momentum, structure). Ties → NEUTRAL.
2. Sums scores. Volatility and S/R contribute regardless of direction.
3. S/R is computed with the aggregate direction as a hint (needs to know
   which side "favorable" is).
4. Collects warnings (e.g. extreme volatility, RSI overbought against direction).

This is deliberately independent from FastAPI so the same engine can run
inside the backtester (Phase 6) exactly as it runs live.
"""
from collections import Counter
from collections.abc import Sequence

from app.services.analysis.momentum import analyze_momentum
from app.services.analysis.structure import analyze_structure
from app.services.analysis.support_resistance import analyze_support_resistance
from app.services.analysis.trend import analyze_trend
from app.services.analysis.types import AnalysisResult, Direction, VolatilityAnalysis
from app.services.analysis.volatility import analyze_volatility
from app.services.indicators.candles import closes as extract_closes
from app.services.indicators.candles import highs as extract_highs
from app.services.indicators.candles import lows as extract_lows
from app.services.market_data.models import Candle


def _majority_direction(dirs: list[Direction]) -> Direction:
    votes = Counter(d for d in dirs if d != Direction.NEUTRAL)
    if not votes:
        return Direction.NEUTRAL
    (top_dir, top_count), *_rest = votes.most_common()
    # A tie means we don't have a clear majority.
    if len(votes) > 1 and votes.most_common()[1][1] == top_count:
        return Direction.NEUTRAL
    return top_dir


def analyze(candles: Sequence[Candle]) -> AnalysisResult:
    close_s = extract_closes(candles)
    high_s = extract_highs(candles)
    low_s = extract_lows(candles)
    price = close_s[-1] if close_s else float("nan")

    trend = analyze_trend(close_s)
    momentum = analyze_momentum(close_s)
    structure = analyze_structure(high_s, low_s, close_s)
    volatility = analyze_volatility(high_s, low_s, close_s)

    direction = _majority_direction([trend.direction, momentum.direction, structure.direction])

    sr = analyze_support_resistance(high_s, low_s, close_s, direction_hint=direction)

    total_score = trend.score + momentum.score + structure.score + sr.score + volatility.score

    reasons: list[str] = []
    for bucket in (trend, momentum, structure, sr, volatility):
        reasons.extend(bucket.reasons)

    warnings = _collect_warnings(volatility, momentum, direction)

    return AnalysisResult(
        direction=direction,
        score=total_score,
        price=price,
        trend=trend,
        momentum=momentum,
        volatility=volatility,
        structure=structure,
        support_resistance=sr,
        reasons=reasons,
        warnings=warnings,
    )


def _collect_warnings(
    volatility: VolatilityAnalysis,
    momentum,  # MomentumAnalysis, avoid circular import
    direction: Direction,
) -> list[str]:
    warnings: list[str] = []
    if volatility.level == "EXTREME":
        warnings.append("Extreme volatility — consider waiting for calmer conditions")
    if direction == Direction.BULLISH and momentum.rsi >= 70:
        warnings.append(f"RSI {momentum.rsi:.1f} overbought — pullback risk")
    if direction == Direction.BEARISH and momentum.rsi <= 30:
        warnings.append(f"RSI {momentum.rsi:.1f} oversold — bounce risk")
    return warnings
