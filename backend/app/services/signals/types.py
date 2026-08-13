"""Signal result types."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class RiskReward:
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float  # TP1 / SL distance ratio
    atr: float
    score: float  # 0..10


@dataclass(frozen=True, slots=True)
class SignalResult:
    """A trading signal for one symbol at one primary timeframe.

    The signal engine's job is to convert AnalysisResults across multiple
    timeframes into an actionable BUY / SELL / WAIT with a confidence score
    and a full audit trail (breakdown + reasons + warnings).
    """

    symbol: str
    direction: SignalDirection
    confidence: float  # 0..100 — analysis(90) + R:R(10)
    timeframe: str  # the primary decision timeframe (e.g. "15m")

    # Trade parameters — only meaningful when direction is BUY or SELL.
    entry: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    risk_reward: float | None

    # Full audit trail.
    breakdown: dict[str, float] = field(default_factory=dict)  # bucket → score contribution
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime | None = None

    @property
    def is_actionable(self) -> bool:
        return self.direction != SignalDirection.WAIT
