"""Portfolio tracking — equity curve, position sizing, peak/drawdown."""
from datetime import datetime


def position_size(
    equity: float,
    risk_pct: float,
    stop_distance: float,
) -> float:
    """Units to buy/sell to risk `risk_pct` of `equity` given the stop distance.

    Example: equity=$10,000, risk_pct=1.0, stop_distance=$7.5
        risk_amount = $100
        units = 100 / 7.5 = 13.33 (oz for XAUUSD)
    """
    if stop_distance <= 0:
        return 0.0
    risk_amount = equity * (risk_pct / 100.0)
    return risk_amount / stop_distance


class Portfolio:
    """Tracks equity through time and computes peak / drawdown live."""

    def __init__(self, initial_equity: float) -> None:
        self._equity = initial_equity
        self._peak = initial_equity
        self._max_drawdown = 0.0
        self._equity_curve: list[tuple[datetime, float]] = []

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def peak(self) -> float:
        return self._peak

    @property
    def max_drawdown(self) -> float:
        return self._max_drawdown

    @property
    def curve(self) -> list[tuple[datetime, float]]:
        return list(self._equity_curve)

    def record(self, timestamp: datetime, equity: float) -> None:
        self._equity = equity
        if equity > self._peak:
            self._peak = equity
        drawdown = self._peak - equity
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown
        self._equity_curve.append((timestamp, equity))
