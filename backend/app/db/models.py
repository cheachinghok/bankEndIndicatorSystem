from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    provider_code: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(128), nullable=True)

    candles: Mapped[list["MarketData"]] = relationship(back_populates="symbol_ref")


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "timestamp", name="uq_market_data_ohlc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)

    symbol_ref: Mapped[Symbol] = relationship(back_populates="candles")


class Signal(Base):
    """A generated trading signal.

    We store every signal (including WAIT), so we can measure the strategy's
    hit rate and calibration over time. The `breakdown`/`reasons`/`warnings`
    JSON columns preserve the full audit trail — the Signal Detail screen
    reads directly from these.
    """
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)  # primary decision TF
    direction: Mapped[str] = mapped_column(String(8), index=True)  # BUY / SELL / WAIT
    confidence: Mapped[float] = mapped_column(Float, index=True)

    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)

    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # bucket → score
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BacktestRun(Base):
    """A stored backtest execution — config + stats + trades + equity curve.

    Trades and equity_curve are stored as JSON for MVP simplicity. If they
    grow too large per run, we'll split into normalized child tables later.
    """
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_code: Mapped[str] = mapped_column(String(16), index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    trades: Mapped[list] = mapped_column(JSON, default=list)
    equity_curve: Mapped[list] = mapped_column(JSON, default=list)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    initial_equity: Mapped[float] = mapped_column(Float)
    final_equity: Mapped[float] = mapped_column(Float)
    from_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    to_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
