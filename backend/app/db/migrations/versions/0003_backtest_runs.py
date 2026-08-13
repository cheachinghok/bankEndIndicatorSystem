"""backtest_runs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol_code", sa.String(16), nullable=False),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("stats", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("trades", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("equity_curve", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("trade_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("initial_equity", sa.Float, nullable=False),
        sa.Column("final_equity", sa.Float, nullable=False),
        sa.Column("from_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("to_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_backtest_runs_symbol_code", "backtest_runs", ["symbol_code"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_symbol_code", table_name="backtest_runs")
    op.drop_table("backtest_runs")
