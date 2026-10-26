"""add license_key to org_settings

Signed license code (plans/v5 2026-10-26-signed-license-keys), verified on
every plan check by app/core/license_gate.py.

Revision ID: b3d9e2a7c415
Revises: a7c1e4f9b2d3
Create Date: 2026-10-25 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d9e2a7c415'
down_revision: Union[str, Sequence[str], None] = 'a7c1e4f9b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('license_key', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('org_settings', 'license_key')
