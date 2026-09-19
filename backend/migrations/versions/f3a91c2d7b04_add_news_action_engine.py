"""add news action engine state + trade journal

Revision ID: f3a91c2d7b04
Revises: e7a1f00d5c42
Create Date: 2026-09-05

News Action Engine: strategies gain pause-audit columns
(paused_reason, news_event_id) and lot-size state
(quantity_multiplier, multiplier_set_at). Advisory-only Claude
output persists in trade_journal.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3a91c2d7b04'
down_revision: Union[str, None] = 'e7a1f00d5c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('strategies', sa.Column('paused_reason', sa.String(length=255), nullable=True))
    op.add_column('strategies', sa.Column('news_event_id', sa.UUID(), nullable=True))
    op.add_column('strategies', sa.Column(
        'quantity_multiplier', sa.Numeric(precision=5, scale=4),
        nullable=False, server_default='1.0000'))
    op.add_column('strategies', sa.Column('multiplier_set_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_strategies_news_event', 'strategies', 'news_articles',
        ['news_event_id'], ['id'], ondelete='SET NULL')

    op.create_table(
        'trade_journal',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('strategy_id', sa.UUID(), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trade_journal_user_id'), 'trade_journal', ['user_id'], unique=False)

    # Calibration history for the impact engine: every signal snapshot
    # keeps its signed impact + band so HIGH/MEDIUM thresholds can be
    # refit by percentile instead of guesswork.
    op.add_column('news_signals', sa.Column('impact', sa.Numeric(precision=8, scale=5),
                                            nullable=False, server_default='0'))
    op.add_column('news_signals', sa.Column('band', sa.String(length=10),
                                            nullable=False, server_default='LOW'))
    op.create_index('ix_news_signals_ticker_band', 'news_signals',
                    ['ticker', 'band'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_news_signals_ticker_band', table_name='news_signals')
    op.drop_column('news_signals', 'band')
    op.drop_column('news_signals', 'impact')
    op.drop_index(op.f('ix_trade_journal_user_id'), table_name='trade_journal')
    op.drop_table('trade_journal')
    op.drop_constraint('fk_strategies_news_event', 'strategies', type_='foreignkey')
    op.drop_column('strategies', 'multiplier_set_at')
    op.drop_column('strategies', 'quantity_multiplier')
    op.drop_column('strategies', 'news_event_id')
    op.drop_column('strategies', 'paused_reason')
