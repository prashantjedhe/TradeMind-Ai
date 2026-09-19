"""add BTST settlement type

Revision ID: 8e4b2c7d1f90
Revises: 7c3e1f2a9b44
"""
from typing import Sequence, Union

from alembic import op

revision: str = "8e4b2c7d1f90"
down_revision: Union[str, None] = "7c3e1f2a9b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum values cannot be removed safely; IF NOT EXISTS keeps
    # this migration idempotent across environments already carrying BTST.
    op.execute("ALTER TYPE settlementtype ADD VALUE IF NOT EXISTS 'BTST'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value in place. Existing
    # BTST rows should be migrated by an operator before downgrading.
    pass
