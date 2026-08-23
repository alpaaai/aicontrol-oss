"""add agent coverage columns

Trimmed to this change only. Autogenerate also reports drift left over from
phase 1's deletes (tables and indexes dropped from the models, never migrated);
that is not this revision's business.

Revision ID: 957deca269b7
Revises: 2b88f1c5d164
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '957deca269b7'
down_revision: Union[str, Sequence[str], None] = '2b88f1c5d164'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("hook", sa.String(length=100), nullable=True))
    op.add_column("agents", sa.Column("sdk_version", sa.String(length=30), nullable=True))
    op.add_column("agents", sa.Column("workflow", sa.String(length=100), nullable=True))
    op.add_column("agents", sa.Column("coverage_last_seen_at", sa.TIMESTAMP(), nullable=True))
    # JSONB rather than ARRAY(String): asyncpg cannot infer an array type from
    # a Python list bound into text() SQL.
    op.add_column("agents", sa.Column(
        "silent_noop_warnings", postgresql.JSONB(astext_type=sa.Text()),
        server_default="[]", nullable=True,
    ))
    op.add_column("agents", sa.Column(
        "unresolved_systems", postgresql.JSONB(astext_type=sa.Text()),
        server_default="[]", nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("agents", "unresolved_systems")
    op.drop_column("agents", "silent_noop_warnings")
    op.drop_column("agents", "coverage_last_seen_at")
    op.drop_column("agents", "workflow")
    op.drop_column("agents", "sdk_version")
    op.drop_column("agents", "hook")
