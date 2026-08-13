"""initial: symbols + market_data

Revision ID: 0001
Revises:
Create Date: 2026-08-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("provider_code", sa.String(32), nullable=False),
        sa.Column("description", sa.String(128), nullable=True),
        sa.UniqueConstraint("code", name="uq_symbols_code"),
    )
    op.create_index("ix_symbols_code", "symbols", ["code"])

    op.create_table(
        "market_data",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "symbol_id",
            sa.Integer,
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "symbol_id", "timeframe", "timestamp", name="uq_market_data_ohlc"
        ),
    )
    op.create_index("ix_market_data_symbol_id", "market_data", ["symbol_id"])
    op.create_index("ix_market_data_timeframe", "market_data", ["timeframe"])
    op.create_index("ix_market_data_timestamp", "market_data", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_market_data_timestamp", table_name="market_data")
    op.drop_index("ix_market_data_timeframe", table_name="market_data")
    op.drop_index("ix_market_data_symbol_id", table_name="market_data")
    op.drop_table("market_data")
    op.drop_index("ix_symbols_code", table_name="symbols")
    op.drop_table("symbols")
