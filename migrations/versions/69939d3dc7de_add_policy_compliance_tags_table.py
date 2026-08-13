"""add policy_compliance_tags table

Revision ID: 69939d3dc7de
Revises: e6d742f68537
Create Date: 2026-08-13 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '69939d3dc7de'
down_revision: Union[str, Sequence[str], None] = 'e6d742f68537'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('policy_compliance_tags',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=False),
    sa.Column('owasp_asi_tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
    sa.Column('nist_rmf_functions', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
    sa.Column('eu_ai_act_articles', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('policy_id')
    )


def downgrade() -> None:
    op.drop_table('policy_compliance_tags')
