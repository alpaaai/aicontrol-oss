"""add_unique_constraint_agents_name

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_agents_name", "agents", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_agents_name", "agents", type_="unique")
