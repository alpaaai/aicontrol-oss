"""rebuild mcp_servers for gateway

Revision ID: f717b57ffd62
Revises: 3c9073bb00c2
Create Date: 2026-09-08 16:15:25.217378

Trimmed to this change only. Autogenerate also proposed dropping tenant_id
columns/indexes across six other tables and an unrelated policies scope
index -- pre-existing drift between current models and the DB, unrelated to
this migration (matching the precedent in
b0347c2a2aaf_add_policy_scope_columns.py). Left untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f717b57ffd62'
down_revision: Union[str, Sequence[str], None] = '3c9073bb00c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete the one stale row left over from the deleted module (name=
    # 'vendor-invoice-mcp', status='pending_scan') -- never swept because no
    # db_hygiene.py rule covered this table. See plan 02 Task 1 discussion.
    op.execute("DELETE FROM mcp_servers")
    op.drop_column('mcp_servers', 'auth_token')
    op.drop_column('mcp_servers', 'auth_type')
    op.add_column('mcp_servers', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.alter_column('mcp_servers', 'status', server_default='pending_review')


def downgrade() -> None:
    op.alter_column('mcp_servers', 'status', server_default='pending_scan')
    op.drop_column('mcp_servers', 'tenant_id')
    op.add_column('mcp_servers', sa.Column('auth_type', sa.String(length=20), server_default='none', nullable=False))
    op.add_column('mcp_servers', sa.Column('auth_token', sa.Text(), nullable=True))
