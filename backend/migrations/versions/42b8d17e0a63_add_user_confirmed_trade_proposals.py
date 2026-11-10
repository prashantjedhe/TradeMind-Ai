"""add persistent user-confirmed trade proposals

Revision ID: 42b8d17e0a63
Revises: 6c1d8a4e2f90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "42b8d17e0a63"
down_revision: Union[str, None] = "6c1d8a4e2f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trade_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_key", sa.String(length=180), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("settlement_type", sa.String(length=12), nullable=False),
        sa.Column("limit_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.String(length=500), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_key", name="uq_trade_proposals_proposal_key"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("ix_trade_proposals_user_id", "trade_proposals", ["user_id"])
    op.create_index("ix_trade_proposals_strategy_id", "trade_proposals", ["strategy_id"])
    op.create_index(
        "ix_trade_proposals_user_status_expiry",
        "trade_proposals",
        ["user_id", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_trade_proposals_user_status_expiry", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_strategy_id", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_user_id", table_name="trade_proposals")
    op.drop_table("trade_proposals")
