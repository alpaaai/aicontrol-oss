"""observe by default

Revision ID: 3c9073bb00c2
Revises: 957deca269b7
Create Date: 2026-08-24 15:58:14.490923

D16: server_default changes new rows only. No UPDATE over existing `agents`
rows -- an agent someone deliberately put into enforcement must not be
quietly disarmed by an upgrade. Two populations exist after this migration:
pre-migration rows defaulting to `govern`, post-migration rows to `observe`.

Autogenerate against the live DB also proposed dropping `tenant_id` columns
and several indexes across six tables -- pre-existing drift between the
current models (which declare no tenant_id) and the DB (which still carries
it from before the overhaul), unrelated to this migration. Left untouched;
out of scope here, relevant to phase-7 task 7.4 (the tenancy seam).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9073bb00c2'
down_revision: Union[str, Sequence[str], None] = '957deca269b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'agents',
        sa.Column('strict_unresolved_system', sa.Boolean(), server_default='false', nullable=False),
    )
    op.alter_column('agents', 'governance_mode', server_default='observe')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('agents', 'governance_mode', server_default='govern')
    op.drop_column('agents', 'strict_unresolved_system')
