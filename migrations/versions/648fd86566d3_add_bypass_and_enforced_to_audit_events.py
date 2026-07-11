"""add bypass and enforced to audit_events

Revision ID: 648fd86566d3
Revises: c018e2f86bdc
Create Date: 2026-07-10 16:33:57.871997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '648fd86566d3'
down_revision: Union[str, Sequence[str], None] = 'c018e2f86bdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_events', sa.Column('bypass', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('audit_events', sa.Column('enforced', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('audit_events', 'enforced')
    op.drop_column('audit_events', 'bypass')
