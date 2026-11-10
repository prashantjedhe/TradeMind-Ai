"""align existing schema with ORM constraints and metric columns

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Migrations previously added these optional metrics as nullable even
    # though the ORM and API expect numeric values on every result.
    for name in (
        "sortino", "calmar", "volatility", "profit_factor",
        "total_fees", "slippage_bps",
    ):
        op.execute(
            sa.text(
                f"UPDATE backtest_results SET {name} = 0 WHERE {name} IS NULL"
            )
        )
        op.alter_column(
            "backtest_results",
            name,
            existing_type=sa.Numeric(),
            nullable=False,
        )

    op.alter_column(
        "backtest_results",
        "efficiency_ratio",
        existing_type=sa.Numeric(precision=6, scale=4),
        type_=sa.Numeric(precision=12, scale=6),
        existing_nullable=False,
        postgresql_using="efficiency_ratio::numeric(12,6)",
    )

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("strategies")}
    if "ix_strategies_status_timeframe" not in indexes:
        op.create_index(
            "ix_strategies_status_timeframe",
            "strategies",
            ["status", "timeframe"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_strategies_status_timeframe",
        table_name="strategies",
    )
    op.alter_column(
        "backtest_results",
        "efficiency_ratio",
        existing_type=sa.Numeric(precision=12, scale=6),
        type_=sa.Numeric(precision=6, scale=4),
        existing_nullable=False,
        postgresql_using="efficiency_ratio::numeric(6,4)",
    )
    for name in (
        "sortino", "calmar", "volatility", "profit_factor",
        "total_fees", "slippage_bps",
    ):
        op.alter_column(
            "backtest_results",
            name,
            existing_type=sa.Numeric(),
            nullable=True,
        )
