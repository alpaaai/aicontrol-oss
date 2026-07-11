"""add mcp_servers table

Revision ID: a268ff087fc0
Revises: 648fd86566d3
Create Date: 2026-07-10 17:07:44.803683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a268ff087fc0'
down_revision: Union[str, Sequence[str], None] = '648fd86566d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mcp_servers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('base_url', sa.Text(), nullable=False),
    sa.Column('auth_type', sa.String(length=20), server_default='none', nullable=False),
    sa.Column('auth_token', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='pending_scan', nullable=False),
    sa.Column('approved_tools', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('mcp_servers')
