"""signals table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "symbol_id",
            sa.Integer,
            sa.ForeignKey("symbols.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("entry", sa.Float, nullable=True),
        sa.Column("stop_loss", sa.Float, nullable=True),
        sa.Column("take_profit_1", sa.Float, nullable=True),
        sa.Column("take_profit_2", sa.Float, nullable=True),
        sa.Column("risk_reward", sa.Float, nullable=True),
        sa.Column("breakdown", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("reasons", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("warnings", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_signals_symbol_id", "signals", ["symbol_id"])
    op.create_index("ix_signals_timeframe", "signals", ["timeframe"])
    op.create_index("ix_signals_direction", "signals", ["direction"])
    op.create_index("ix_signals_confidence", "signals", ["confidence"])
    op.create_index("ix_signals_generated_at", "signals", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_signals_generated_at", table_name="signals")
    op.drop_index("ix_signals_confidence", table_name="signals")
    op.drop_index("ix_signals_direction", table_name="signals")
    op.drop_index("ix_signals_timeframe", table_name="signals")
    op.drop_index("ix_signals_symbol_id", table_name="signals")
    op.drop_table("signals")
