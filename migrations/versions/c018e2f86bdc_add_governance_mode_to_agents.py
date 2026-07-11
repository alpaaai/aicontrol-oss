"""add governance_mode to agents

Revision ID: c018e2f86bdc
Revises: c3d4e5f6a7b8
Create Date: 2026-07-10 16:29:26.180737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c018e2f86bdc'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('governance_mode', sa.String(length=20), server_default='govern', nullable=False))


def downgrade() -> None:
    op.drop_column('agents', 'governance_mode')
