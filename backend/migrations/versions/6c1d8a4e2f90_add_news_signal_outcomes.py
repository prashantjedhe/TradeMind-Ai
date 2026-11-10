"""add auditable forward outcomes for qualified news signals

Revision ID: 6c1d8a4e2f90
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c1d8a4e2f90"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_signal_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("signal_id", sa.UUID(), nullable=False),
        sa.Column("horizon_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("forecast_direction", sa.String(length=8), nullable=False),
        sa.Column("signal_impact", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("signal_band", sa.String(length=10), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_price", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("return_fraction", sa.Numeric(precision=12, scale=8), nullable=False),
        sa.Column("directional_hit", sa.Boolean(), nullable=True),
        sa.Column("actual_horizon_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["news_signals.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "signal_id", "horizon_minutes",
            name="uq_news_outcome_signal_horizon",
        ),
    )
    op.create_index(
        "ix_news_signal_outcomes_signal_id",
        "news_signal_outcomes",
        ["signal_id"],
    )
    op.create_index(
        "ix_news_outcomes_horizon_target",
        "news_signal_outcomes",
        ["horizon_minutes", "target_timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_outcomes_horizon_target", table_name="news_signal_outcomes")
    op.drop_index("ix_news_signal_outcomes_signal_id", table_name="news_signal_outcomes")
    op.drop_table("news_signal_outcomes")
