"""Multi-timeframe agreement rules.

Timeframe hierarchy (per project spec):
    4H  = Major trend        (hardest gate — must be BULL or BEAR, not NEUTRAL)
    1H  = Trend confirmation (must agree with 4H)
    15M = Trading setup      (primary decision timeframe)
    5M  = Entry confirmation (fine-tunes confidence, not a hard gate)

WAIT criteria (any one → WAIT):
    - 4H is NEUTRAL
    - 4H and 1H disagree (opposite directions)
    - 15M disagrees with 4H+1H direction

Confidence weights when signal fires (blend across TFs):
    4H = 40%, 1H = 30%, 15M = 20%, 5M = 10%
    (higher timeframes are more reliable)
"""
from dataclasses import dataclass

from app.services.analysis.types import AnalysisResult, Direction
from app.services.signals.types import SignalDirection

TIMEFRAME_WEIGHTS: dict[str, float] = {
    "4h": 0.40,
    "1h": 0.30,
    "15m": 0.20,
    "5m": 0.10,
}

PRIMARY_TIMEFRAME = "15m"
GATE_TIMEFRAMES = ("4h", "1h", "15m")


@dataclass(frozen=True, slots=True)
class MtfDecision:
    direction: SignalDirection
    reason: str  # what determined the direction (for the reasons list)


def multi_timeframe_gate(analyses: dict[str, AnalysisResult]) -> MtfDecision:
    """Apply the WAIT gates. Returns BUY, SELL, or WAIT with a reason."""
    tf4h = analyses.get("4h")
    tf1h = analyses.get("1h")
    tf15 = analyses.get("15m")

    missing = [tf for tf in GATE_TIMEFRAMES if analyses.get(tf) is None]
    if missing:
        return MtfDecision(
            SignalDirection.WAIT,
            f"Missing analysis for required timeframe(s): {', '.join(missing)}",
        )

    assert tf4h and tf1h and tf15  # for type-checker; missing is covered above

    if tf4h.direction == Direction.NEUTRAL:
        return MtfDecision(SignalDirection.WAIT, "4H trend is NEUTRAL — no clear direction")

    if tf1h.direction != Direction.NEUTRAL and tf1h.direction != tf4h.direction:
        return MtfDecision(
            SignalDirection.WAIT,
            f"1H ({tf1h.direction.value}) disagrees with 4H ({tf4h.direction.value})",
        )

    if tf15.direction != Direction.NEUTRAL and tf15.direction != tf4h.direction:
        return MtfDecision(
            SignalDirection.WAIT,
            f"15M ({tf15.direction.value}) disagrees with 4H ({tf4h.direction.value})",
        )

    # All gates pass — the direction is 4H's direction.
    direction = SignalDirection.BUY if tf4h.direction == Direction.BULLISH else SignalDirection.SELL
    return MtfDecision(
        direction,
        f"4H+1H+15M aligned {tf4h.direction.value}",
    )


def blended_analysis_score(analyses: dict[str, AnalysisResult]) -> float:
    """Weighted average of analysis scores across timeframes.

    Weights: 4H=0.40, 1H=0.30, 15M=0.20, 5M=0.10. Missing TFs are skipped
    and the remaining weights are renormalized so the result stays in 0..90.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for tf, weight in TIMEFRAME_WEIGHTS.items():
        r = analyses.get(tf)
        if r is None:
            continue
        weighted_sum += r.score * weight
        total_weight += weight
    if total_weight == 0.0:
        return 0.0
    return weighted_sum / total_weight
