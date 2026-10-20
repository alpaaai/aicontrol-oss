"""add_audit_and_review_query_indexes

audit_events had no index on created_at, so the retention purge, the audit
list (ORDER BY created_at DESC) and the dashboard window queries each
sequentially scanned the whole table -- a cost that grows with retention.
hitl_reviews.audit_event_id (FK, used by the purge and the review-queue join)
and sessions.agent_id had no index either.

Revision ID: a7c1e4f9b2d3
Revises: 6e395c35ae43
Create Date: 2026-10-20 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c1e4f9b2d3'
down_revision: Union[str, Sequence[str], None] = '6e395c35ae43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])
    op.create_index('ix_hitl_reviews_audit_event_id', 'hitl_reviews', ['audit_event_id'])
    op.create_index('ix_hitl_reviews_status_created_at', 'hitl_reviews', ['status', 'created_at'])
    op.create_index('ix_sessions_agent_id', 'sessions', ['agent_id'])


def downgrade() -> None:
    op.drop_index('ix_sessions_agent_id', table_name='sessions')
    op.drop_index('ix_hitl_reviews_status_created_at', table_name='hitl_reviews')
    op.drop_index('ix_hitl_reviews_audit_event_id', table_name='hitl_reviews')
    op.drop_index('ix_audit_events_created_at', table_name='audit_events')
