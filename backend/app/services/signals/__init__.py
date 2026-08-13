"""Signal engine — takes multi-timeframe analysis and emits BUY/SELL/WAIT.

Public API:
    SignalDirection (enum)
    RiskReward, SignalResult (dataclasses)
    generate_signal(symbol, analyses_by_tf) → SignalResult

Notes:
- The engine is a pure function. Same input → same output. No I/O, no
  FastAPI, no DB — the exact same engine runs live and inside the backtester.
- Confidence is the strength of the setup vs. the strategy, NOT a probability
  of winning. Display UI must reflect this (label as "Setup Strength").
"""
from app.services.signals.engine import generate_signal
from app.services.signals.risk import compute_risk_reward
from app.services.signals.types import RiskReward, SignalDirection, SignalResult

__all__ = [
    "RiskReward",
    "SignalDirection",
    "SignalResult",
    "compute_risk_reward",
    "generate_signal",
]
