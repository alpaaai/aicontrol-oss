"""add_compliance_reports

Revision ID: 35abf3c7a3b6
Revises: 976c0b6d086a
Create Date: 2026-05-28 09:05:45.010325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '35abf3c7a3b6'
down_revision: Union[str, Sequence[str], None] = '976c0b6d086a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'compliance_reports',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('generated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),
        sa.Column('frameworks', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('format', sa.String(length=10), nullable=False),
        sa.Column('generated_by', sa.UUID(), nullable=True),
        sa.Column('report_path', sa.Text(), nullable=False),
        sa.Column('md_path', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(length=100), nullable=False),
        sa.Column('mock_used', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('token_input', sa.Integer(), nullable=True),
        sa.Column('token_output', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('compliance_reports')
