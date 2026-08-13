"""add discovered_agents table

Revision ID: 503ace6bc81c
Revises: a268ff087fc0
Create Date: 2026-07-12 14:47:10.991027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '503ace6bc81c'
down_revision: Union[str, Sequence[str], None] = 'a268ff087fc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Autogenerate also detected a set of unrelated `tenant_id` column/index/
    constraint drops across agents/api_tokens/audit_events/hitl_reviews/
    policies/sessions/policy_warnings -- pre-existing drift between this dev
    database and the current ORM models, unrelated to this migration's
    actual purpose. Stripped out deliberately, not applied here: dropping
    those is a separate, out-of-scope decision that shouldn't ride along
    with an unrelated new-table migration.
    """
    op.create_table('discovered_agents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('confidence', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('promoted_agent_id', sa.UUID(), nullable=True),
    sa.Column('discovered_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['promoted_agent_id'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'external_id', name='uq_discovered_agents_source_external_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('discovered_agents')
