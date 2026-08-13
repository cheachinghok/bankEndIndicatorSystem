"""Risk / Reward calculation.

Given a direction (BUY/SELL), current price, and ATR, produce entry / stop
loss / two take-profit targets and compute the R:R ratio. Score 0..10
based on how favorable the R:R is (10 for ≥2.5, scaled to 0 for <1.0).

Defaults are XAUUSD-tuned: SL = 1.5 × ATR (roughly one candle's noise),
TP1 = 3.0 × ATR (R:R = 2.0), TP2 = 4.5 × ATR (R:R = 3.0).
"""
import math

from app.services.signals.types import RiskReward, SignalDirection

SL_ATR_MULT = 1.5
TP1_ATR_MULT = 3.0
TP2_ATR_MULT = 4.5

MIN_RR_FOR_ANY_POINTS = 1.0
FULL_POINTS_AT_RR = 2.5
RR_MAX_POINTS = 10.0


def compute_risk_reward(
    direction: SignalDirection,
    price: float,
    atr: float,
    *,
    sl_mult: float = SL_ATR_MULT,
    tp1_mult: float = TP1_ATR_MULT,
    tp2_mult: float = TP2_ATR_MULT,
) -> RiskReward:
    if direction == SignalDirection.WAIT:
        raise ValueError("R:R only defined for BUY/SELL")
    if math.isnan(atr) or atr <= 0:
        # Unusable ATR — emit a zeroed RiskReward with zero score.
        return RiskReward(
            entry=price,
            stop_loss=price,
            take_profit_1=price,
            take_profit_2=price,
            risk_reward=0.0,
            atr=atr,
            score=0.0,
        )

    if direction == SignalDirection.BUY:
        sl = price - sl_mult * atr
        tp1 = price + tp1_mult * atr
        tp2 = price + tp2_mult * atr
    else:  # SELL
        sl = price + sl_mult * atr
        tp1 = price - tp1_mult * atr
        tp2 = price - tp2_mult * atr

    risk = abs(price - sl)
    reward = abs(tp1 - price)
    rr = reward / risk if risk > 0 else 0.0

    if rr < MIN_RR_FOR_ANY_POINTS:
        score = 0.0
    elif rr >= FULL_POINTS_AT_RR:
        score = RR_MAX_POINTS
    else:
        # Linear scale between MIN and FULL.
        span = FULL_POINTS_AT_RR - MIN_RR_FOR_ANY_POINTS
        score = RR_MAX_POINTS * (rr - MIN_RR_FOR_ANY_POINTS) / span

    return RiskReward(
        entry=price,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
        atr=atr,
        score=round(score, 2),
    )
