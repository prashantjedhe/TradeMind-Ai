"""add news intelligence tables (articles, sentiment, signals)

Revision ID: e7a1f00d5c42
Revises: d4fc31c06a47
Create Date: 2026-09-05

Free-RSS news phase: raw headlines (EN+HI) -> per-ticker scores ->
aggregated signal snapshots the strategy evaluator reads.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e7a1f00d5c42'
down_revision: Union[str, None] = 'd4fc31c06a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'news_articles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=60), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('url_hash', sa.String(length=64), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=8), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tickers', postgresql.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column('sector', sa.String(length=20), nullable=False),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url', name='uq_news_articles_url'),
        sa.UniqueConstraint('url_hash', name='uq_news_articles_url_hash'),
    )
    op.create_index(op.f('ix_news_articles_url_hash'), 'news_articles', ['url_hash'], unique=False)
    op.create_index(op.f('ix_news_articles_published_at'), 'news_articles', ['published_at'], unique=False)
    op.create_index('ix_news_articles_tickers', 'news_articles', ['tickers'],
                    unique=False, postgresql_using='gin')

    op.create_table(
        'news_sentiment',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('article_id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('score', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('magnitude', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('label', sa.String(length=8), nullable=False),
        sa.Column('model_version', sa.String(length=30), nullable=False),
        sa.Column('spans', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('article_id', name='uq_news_sentiment_article'),
    )
    op.create_index(op.f('ix_news_sentiment_ticker'), 'news_sentiment', ['ticker'], unique=False)
    op.create_index(op.f('ix_news_sentiment_created_at'), 'news_sentiment', ['created_at'], unique=False)
    op.create_index('ix_news_sentiment_ticker_created', 'news_sentiment', ['ticker', 'created_at'],
                    unique=False)

    op.create_table(
        'news_signals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('window_minutes', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('score', sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column('zscore', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('article_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'window_minutes', 'timestamp', name='uq_news_signal_bucket'),
    )
    op.create_index(op.f('ix_news_signals_ticker'), 'news_signals', ['ticker'], unique=False)
    op.create_index(op.f('ix_news_signals_timestamp'), 'news_signals', ['timestamp'], unique=False)
    op.create_index('ix_news_signals_ticker_window_ts', 'news_signals',
                    ['ticker', 'window_minutes', 'timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_news_signals_ticker_window_ts', table_name='news_signals')
    op.drop_index(op.f('ix_news_signals_timestamp'), table_name='news_signals')
    op.drop_index(op.f('ix_news_signals_ticker'), table_name='news_signals')
    op.drop_table('news_signals')
    op.drop_index('ix_news_sentiment_ticker_created', table_name='news_sentiment')
    op.drop_index(op.f('ix_news_sentiment_created_at'), table_name='news_sentiment')
    op.drop_index(op.f('ix_news_sentiment_ticker'), table_name='news_sentiment')
    op.drop_table('news_sentiment')
    op.drop_index('ix_news_articles_tickers', table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_published_at'), table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_url_hash'), table_name='news_articles')
    op.drop_table('news_articles')
