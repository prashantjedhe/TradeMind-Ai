"""sync backtest result schema with the current model

Revision ID: b2f4d8e6a103
Revises: 9a6e2d4c1f88
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b2f4d8e6a103"
down_revision: Union[str, None] = "9a6e2d4c1f88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    backtest_kind = postgresql.ENUM(
        "STANDARD", "WALK_FORWARD", name="backtestkind", create_type=False
    )
    bind = op.get_bind()
    backtest_kind.create(bind, checkfirst=True)

    op.add_column(
        "backtest_results",
        sa.Column("kind", backtest_kind, nullable=False, server_default="STANDARD"),
    )
    op.create_index("ix_backtest_results_kind", "backtest_results", ["kind"])
    for name, column in (
        ("error_message", sa.String(length=500)),
        ("sortino", sa.Numeric(12, 6),),
        ("calmar", sa.Numeric(12, 6),),
        ("volatility", sa.Numeric(12, 6),),
        ("profit_factor", sa.Numeric(12, 6),),
        ("total_fees", sa.Numeric(14, 4),),
        ("slippage_bps", sa.Numeric(10, 4),),
        ("sl_pct", sa.Numeric(8, 6),),
        ("tp_pct", sa.Numeric(8, 6),),
        ("trade_ledger", postgresql.JSONB()),
        ("assumptions", postgresql.JSONB()),
    ):
        op.add_column("backtest_results", sa.Column(name, column, nullable=True))
    op.alter_column("backtest_results", "kind", server_default=None)


def downgrade() -> None:
    for name in (
        "assumptions", "trade_ledger", "tp_pct", "sl_pct", "slippage_bps",
        "total_fees", "profit_factor", "volatility", "calmar", "sortino",
        "error_message",
    ):
        op.drop_column("backtest_results", name)
    op.drop_index("ix_backtest_results_kind", table_name="backtest_results")
    op.drop_column("backtest_results", "kind")
    postgresql.ENUM(name="backtestkind").drop(op.get_bind(), checkfirst=True)
