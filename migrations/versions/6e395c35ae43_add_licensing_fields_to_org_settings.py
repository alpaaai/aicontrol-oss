"""add licensing fields to org_settings

Trimmed to this change only. Autogenerate also reports drift left over from
phase 1's deletes (tenant_id/index cleanup, never migrated); that is not
this revision's business (see 957deca269b7 for the same pattern).

Revision ID: 6e395c35ae43
Revises: f717b57ffd62
Create Date: 2026-09-16 18:02:58.172988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e395c35ae43'
down_revision: Union[str, Sequence[str], None] = 'f717b57ffd62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('license_plan', sa.String(length=20), nullable=True))
    op.add_column('org_settings', sa.Column('license_status', sa.String(length=20), nullable=True))
    op.add_column('org_settings', sa.Column('license_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('org_settings', sa.Column('activation_code', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('org_settings', 'activation_code')
    op.drop_column('org_settings', 'license_synced_at')
    op.drop_column('org_settings', 'license_status')
    op.drop_column('org_settings', 'license_plan')
