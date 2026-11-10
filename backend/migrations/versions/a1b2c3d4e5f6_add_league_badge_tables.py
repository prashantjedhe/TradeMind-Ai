"""add league and badge tables

Revision ID: a1b2c3d4e5f6
Revises: b2f4d8e6a103
Create Date: 2026-09-26 01:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b2f4d8e6a103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum types if not exists
    league_competition = postgresql.ENUM(
        'ACTIVE', 'COMPLETED', 'UPCOMING', name='leaguecompetition', create_type=False
    )
    badge_type = postgresql.ENUM(
        'Consistent Performer', 'Drawdown Master', 'News Ninja', 'Top Trader', 'Marathon Bet', 'First Win',
        name='badgetype', create_type=False
    )
    bind = op.get_bind()
    league_competition.create(bind, checkfirst=True)
    badge_type.create(bind, checkfirst=True)
    existing_tables = set(sa.inspect(bind).get_table_names())

    # 2. Create leagues table
    if 'leagues' not in existing_tables:
        op.create_table(
        'leagues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('initial_balance', sa.Numeric(precision=14, scale=4), nullable=False, server_default='1000000'),
        sa.Column('status', league_competition, nullable=False, server_default='ACTIVE'),
        sa.Column('ranking_metric', sa.String(length=20), nullable=False, server_default='sharpe'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        )
    existing_tables.add('leagues')

    # 3. Create league_entries table
    if 'league_entries' not in existing_tables:
        op.create_table(
        'league_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('league_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('final_sharpe', sa.Numeric(precision=12, scale=6), nullable=False, server_default='0'),
        sa.Column('final_return_pct', sa.Numeric(precision=8, scale=4), nullable=False, server_default='0'),
        sa.Column('final_drawdown', sa.Numeric(precision=12, scale=6), nullable=False, server_default='0'),
        sa.Column('final_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('final_win_rate', sa.Numeric(precision=6, scale=4), nullable=False, server_default='0'),
        sa.Column('final_pnl', sa.Numeric(precision=14, scale=4), nullable=False, server_default='0'),
        sa.Column('final_rank', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        )

    # 4. Create badges table
    if 'badges' not in existing_tables:
        op.create_table(
        'badges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('league_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('badge_type', badge_type, nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('awarded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        )

    def ensure_index(name: str, table: str, columns: list[str], unique: bool = False) -> None:
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
        if name not in indexes:
            op.create_index(name, table, columns, unique=unique)

    ensure_index("ix_league_active", "leagues", ["status"])
    ensure_index(
        "ix_league_entry_league_user",
        "league_entries",
        ["league_id", "user_id"],
        unique=True,
    )
    ensure_index("ix_league_entries_league_id", "league_entries", ["league_id"])
    ensure_index("ix_league_entries_user_id", "league_entries", ["user_id"])

    # A participant can earn multiple distinct badges in one league, but
    # should not receive the same badge type more than once.
    indexes = {item["name"]: item for item in sa.inspect(bind).get_indexes("badges")}
    old_badge_index = indexes.get("ix_badge_league_user")
    if old_badge_index is not None:
        op.drop_index("ix_badge_league_user", table_name="badges")
    ensure_index(
        "ix_badge_league_user_type",
        "badges",
        ["league_id", "user_id", "badge_type"],
        unique=True,
    )
    ensure_index("ix_badges_league_id", "badges", ["league_id"])
    ensure_index("ix_badges_user_id", "badges", ["user_id"])


def downgrade() -> None:
    op.drop_table('badges')
    op.drop_table('league_entries')
    op.drop_table('leagues')
    bind = op.get_bind()
    postgresql.ENUM(name='badgetype').drop(bind, checkfirst=True)
    postgresql.ENUM(name='leaguecompetition').drop(bind, checkfirst=True)
