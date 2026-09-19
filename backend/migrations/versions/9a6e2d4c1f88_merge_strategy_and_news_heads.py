"""merge strategy and news migration branches

Revision ID: 9a6e2d4c1f88
Revises: f3a91c2d7b04, 8e4b2c7d1f90
"""
from typing import Sequence, Union


revision: str = "9a6e2d4c1f88"
down_revision: Union[str, tuple[str, str], None] = (
    "f3a91c2d7b04",
    "8e4b2c7d1f90",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
