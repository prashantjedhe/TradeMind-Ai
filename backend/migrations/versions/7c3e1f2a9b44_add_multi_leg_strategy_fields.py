"""add optional multi-leg strategy configuration

Revision ID: 7c3e1f2a9b44
Revises: d4fc31c06a47
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7c3e1f2a9b44"
down_revision: Union[str, None] = "d4fc31c06a47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("strategies", "root_condition", nullable=True)
    for name, column in (
        ("strategy_type", sa.String(length=20)),
        ("reference", sa.String(length=10)),
        ("product", sa.String(length=20)),
        ("order_mode", sa.String(length=10)),
        ("start_time", sa.Time()),
        ("square_off_time", sa.Time()),
        ("trading_days", postgresql.JSONB()),
        ("legs", postgresql.JSONB()),
        ("risk_controls", postgresql.JSONB()),
    ):
        op.add_column("strategies", sa.Column(name, column, nullable=True))


def downgrade() -> None:
    for name in (
        "risk_controls", "legs", "trading_days", "square_off_time",
        "start_time", "order_mode", "product", "reference", "strategy_type",
    ):
        op.drop_column("strategies", name)
    op.alter_column("strategies", "root_condition", nullable=False)
