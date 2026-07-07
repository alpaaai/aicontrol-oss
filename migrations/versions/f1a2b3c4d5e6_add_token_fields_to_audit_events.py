"""add_token_fields_to_audit_events

Revision ID: f1a2b3c4d5e6
Revises: dfb1e5af00c3
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'dfb1e5af00c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_events", "cost_usd")
    op.drop_column("audit_events", "output_tokens")
    op.drop_column("audit_events", "input_tokens")
