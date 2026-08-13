"""Market analysis engine.

Consumes indicators (Phase 3) and returns per-bucket direction + score
for one timeframe of candles. The signal engine (Phase 5) combines results
across multiple timeframes.

Scoring buckets (weights from the project spec):
    Trend:              25 points
    Momentum:           20 points
    Structure:          20 points
    Support/Resistance: 15 points
    Volatility:         10 points
    ────────────────────────────
    Total (analysis):   90 points   (R:R = 10 points is added by signal engine)

Public API:
    Direction (enum)
    AnalysisResult, TrendAnalysis, MomentumAnalysis,
    VolatilityAnalysis, StructureAnalysis, SupportResistanceAnalysis
    analyze(candles) → AnalysisResult
"""
from app.services.analysis.engine import analyze
from app.services.analysis.types import (
    AnalysisResult,
    Direction,
    MomentumAnalysis,
    StructureAnalysis,
    SupportResistanceAnalysis,
    TrendAnalysis,
    VolatilityAnalysis,
)

__all__ = [
    "AnalysisResult",
    "Direction",
    "MomentumAnalysis",
    "StructureAnalysis",
    "SupportResistanceAnalysis",
    "TrendAnalysis",
    "VolatilityAnalysis",
    "analyze",
]
