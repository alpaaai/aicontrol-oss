"""add_rate_limit_indexes

Revision ID: 976c0b6d086a
Revises: d3bd8dda9119
Create Date: 2026-05-27 22:59:10.261360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '976c0b6d086a'
down_revision: Union[str, Sequence[str], None] = 'd3bd8dda9119'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_audit_events_session_tool',
        'audit_events',
        ['session_id', 'tool_name'],
    )
    op.create_index(
        'ix_audit_events_agent_tool_time',
        'audit_events',
        ['agent_id', 'tool_name', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_audit_events_agent_tool_time', table_name='audit_events')
    op.drop_index('ix_audit_events_session_tool', table_name='audit_events')
