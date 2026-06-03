"""add_library_priority_category_to_policies

Revision ID: dfb1e5af00c3
Revises: b3733c334f75
Create Date: 2026-06-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dfb1e5af00c3'
down_revision: Union[str, Sequence[str], None] = 'b3733c334f75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("library", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "policies",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "policies",
        sa.Column("category", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("policies", "category")
    op.drop_column("policies", "priority")
    op.drop_column("policies", "library")
