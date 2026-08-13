"""add audit_export_configs table

Revision ID: e6d742f68537
Revises: 503ace6bc81c
Create Date: 2026-08-13 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6d742f68537'
down_revision: Union[str, Sequence[str], None] = '503ace6bc81c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_export_configs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('export_type', sa.String(length=20), nullable=False),
    sa.Column('target_url', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('audit_export_configs')
