"""Analysis result types.

Each bucket returns a `direction` (BULLISH/BEARISH/NEUTRAL), a `score`
(0..max points for that bucket), and human-readable `reasons` — the reasons
are what the Signal Detail screen displays to explain WHY a signal fired.
"""
from dataclasses import dataclass, field
from enum import Enum


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


# Point ceilings per bucket — match the plan §4.
TREND_MAX = 25
MOMENTUM_MAX = 20
STRUCTURE_MAX = 20
SUPPORT_RESISTANCE_MAX = 15
VOLATILITY_MAX = 10

ANALYSIS_MAX = (
    TREND_MAX
    + MOMENTUM_MAX
    + STRUCTURE_MAX
    + SUPPORT_RESISTANCE_MAX
    + VOLATILITY_MAX
)  # 90 — the signal engine adds 10 for R:R to reach 100.


@dataclass(frozen=True, slots=True)
class TrendAnalysis:
    direction: Direction
    score: float
    ema20: float
    ema50: float
    ema200: float
    price: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MomentumAnalysis:
    direction: Direction
    score: float
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VolatilityAnalysis:
    score: float
    atr: float
    atr_pct: float  # ATR as % of price
    level: str  # "LOW" | "NORMAL" | "HIGH" | "EXTREME"
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StructureAnalysis:
    direction: Direction
    score: float
    swing_highs: list[float]
    swing_lows: list[float]
    bos: bool  # break of structure in the trend direction
    choch: bool  # change of character (break against prior trend)
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SupportResistanceAnalysis:
    score: float
    nearest_support: float | None
    nearest_resistance: float | None
    distance_to_support_atr: float | None  # in ATR units
    distance_to_resistance_atr: float | None
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Full per-timeframe analysis. Signal engine (Phase 5) combines across timeframes."""
    direction: Direction  # aggregate direction (majority of BULLISH/BEARISH signals)
    score: float  # sum of bucket scores (max 90)
    price: float
    trend: TrendAnalysis
    momentum: MomentumAnalysis
    volatility: VolatilityAnalysis
    structure: StructureAnalysis
    support_resistance: SupportResistanceAnalysis
    reasons: list[str] = field(default_factory=list)  # aggregated from buckets
    warnings: list[str] = field(default_factory=list)  # e.g. "extreme volatility"
