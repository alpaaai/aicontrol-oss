"""add audit_event workflow

Autogenerate also reported drift unrelated to this change (tables and indexes
phase 1 deleted from the models but never dropped in a migration). That drift
is left alone deliberately -- this revision does one thing.

Revision ID: 2b88f1c5d164
Revises: c1f5a8e42b70
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2b88f1c5d164'
down_revision: Union[str, Sequence[str], None] = 'c1f5a8e42b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("workflow", sa.String(length=100), nullable=True))
    # workflow is the grouping dimension for the landing screen and for
    # compliance reports -- both filter on it, so it is indexed from the start.
    op.create_index("ix_audit_events_workflow", "audit_events", ["workflow"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_workflow", table_name="audit_events")
    op.drop_column("audit_events", "workflow")
