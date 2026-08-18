"""Signal engine — the top-level generate_signal function.

Consumes AnalysisResult for each timeframe, applies the multi-timeframe
gate, computes R:R against the primary timeframe's ATR, and returns a
SignalResult with confidence 0..100 and a full audit trail.
"""
from datetime import UTC, datetime

from app.services.analysis.types import AnalysisResult
from app.services.signals.risk import compute_risk_reward
from app.services.signals.rules import (
    PRIMARY_TIMEFRAME,
    blended_analysis_score,
    check_pullback,
    multi_timeframe_gate,
)
from app.services.signals.types import SignalDirection, SignalResult


def generate_signal(
    symbol: str,
    analyses: dict[str, AnalysisResult],
    *,
    now: datetime | None = None,
) -> SignalResult:
    """Emit a BUY/SELL/WAIT signal for `symbol` from per-timeframe analyses.

    Args:
        symbol: e.g. "XAUUSD"
        analyses: mapping of timeframe string ("4h", "1h", "15m", "5m")
                  to AnalysisResult. 4h/1h/15m are required for a firing
                  signal; 5m is optional and contributes to confidence only.
        now: injected timestamp for deterministic testing.

    Returns:
        SignalResult. If any gate fails, direction=WAIT and entry/SL/TP are None.
    """
    now = now or datetime.now(UTC)
    primary = analyses.get(PRIMARY_TIMEFRAME)

    gate = multi_timeframe_gate(analyses)
    if gate.direction == SignalDirection.WAIT:
        # Fallback: pullback-in-trend can still fire even when the strict
        # MTF agreement gate rejects.
        pullback = check_pullback(analyses)
        if pullback is not None:
            gate = pullback  # override with pullback decision
        else:
            return SignalResult(
                symbol=symbol,
                direction=SignalDirection.WAIT,
                confidence=0.0,
                timeframe=PRIMARY_TIMEFRAME,
                entry=None,
                stop_loss=None,
                take_profit_1=None,
                take_profit_2=None,
                risk_reward=None,
                breakdown={"gate": 0.0},
                reasons=[gate.reason],
                warnings=[w for r in analyses.values() for w in r.warnings],
                generated_at=now,
            )

    assert primary is not None  # gate guarantees 15m exists

    analysis_score = blended_analysis_score(analyses)  # 0..90
    rr = compute_risk_reward(gate.direction, primary.price, primary.volatility.atr)
    confidence = round(analysis_score + rr.score, 2)  # 0..100

    reasons: list[str] = [gate.reason]
    for tf in ("4h", "1h", "15m", "5m"):
        a = analyses.get(tf)
        if a is None:
            continue
        for reason in a.reasons:
            reasons.append(f"[{tf}] {reason}")
    reasons.append(f"R:R = 1:{rr.risk_reward:.2f} (score {rr.score:.1f}/10)")

    warnings: list[str] = []
    for a in analyses.values():
        warnings.extend(a.warnings)

    breakdown: dict[str, float] = {
        "analysis_blended": round(analysis_score, 2),
        "risk_reward": rr.score,
    }
    for tf, a in analyses.items():
        breakdown[f"score_{tf}"] = round(a.score, 2)

    return SignalResult(
        symbol=symbol,
        direction=gate.direction,
        confidence=confidence,
        timeframe=PRIMARY_TIMEFRAME,
        entry=rr.entry,
        stop_loss=rr.stop_loss,
        take_profit_1=rr.take_profit_1,
        take_profit_2=rr.take_profit_2,
        risk_reward=rr.risk_reward,
        breakdown=breakdown,
        reasons=reasons,
        warnings=warnings,
        generated_at=now,
    )
