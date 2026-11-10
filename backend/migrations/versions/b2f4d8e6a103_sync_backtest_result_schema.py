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
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "backtest_results" not in existing_tables:
        backtest_status = postgresql.ENUM(
            "DRAFT", "RUNNING", "COMPLETE", "FAILED",
            name="backteststatus",
            create_type=False,
        )
        backtest_status.create(bind, checkfirst=True)
        op.create_table(
            "backtest_results",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "strategy_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("strategies.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("ticker", sa.String(length=20), nullable=False),
            sa.Column("timeframe", sa.String(length=10), nullable=False),
            sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("train_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("train_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("test_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("test_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", backtest_status, nullable=False),
            sa.Column("cagr", sa.Numeric(12, 6), nullable=False),
            sa.Column("sharpe", sa.Numeric(12, 6), nullable=False),
            sa.Column("max_drawdown", sa.Numeric(12, 6), nullable=False),
            sa.Column("win_rate", sa.Numeric(6, 4), nullable=False),
            sa.Column("total_trades", sa.Integer(), nullable=False),
            sa.Column("total_pnl", sa.Numeric(14, 4), nullable=False),
            sa.Column("final_equity", sa.Numeric(14, 4), nullable=False),
            sa.Column("initial_capital", sa.Numeric(14, 4), nullable=False),
            sa.Column("is_sharpe", sa.Numeric(12, 6), nullable=False),
            sa.Column("oos_sharpe", sa.Numeric(12, 6), nullable=False),
            sa.Column("efficiency_ratio", sa.Numeric(6, 4), nullable=False),
            sa.Column("num_windows", sa.Integer(), nullable=False),
            sa.Column("window_results", postgresql.JSONB(), nullable=True),
            sa.Column("equity_curve", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_backtest_results_user_id", "backtest_results", ["user_id"])
        op.create_index("ix_backtest_results_status", "backtest_results", ["status"])
        op.create_index("ix_backtest_user_status", "backtest_results", ["user_id", "status"])

    backtest_kind = postgresql.ENUM(
        "STANDARD", "WALK_FORWARD", name="backtestkind", create_type=False
    )
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
