"""add_policy_warnings_table

Revision ID: d3bd8dda9119
Revises: 93b453657c1a
Create Date: 2026-05-27 22:33:04.269521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3bd8dda9119'
down_revision: Union[str, Sequence[str], None] = '93b453657c1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policy_warnings',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('warning_type', sa.String(50), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=True),
        sa.Column('policy_id', sa.UUID(), nullable=True),
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_warnings_active', 'policy_warnings',
                    ['is_active', 'warning_type'])
    op.create_index('ix_policy_warnings_agent', 'policy_warnings', ['agent_id'],
                    postgresql_where=sa.text('agent_id IS NOT NULL'))
    op.create_index('ix_policy_warnings_policy', 'policy_warnings', ['policy_id'],
                    postgresql_where=sa.text('policy_id IS NOT NULL'))


def downgrade() -> None:
    op.drop_index('ix_policy_warnings_policy', table_name='policy_warnings')
    op.drop_index('ix_policy_warnings_agent', table_name='policy_warnings')
    op.drop_index('ix_policy_warnings_active', table_name='policy_warnings')
    op.drop_table('policy_warnings')
