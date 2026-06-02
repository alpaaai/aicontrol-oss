"""onboarding_identity

Revision ID: b3733c334f75
Revises: 34e7b92670d9
Create Date: 2026-06-02 12:44:40.115748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3733c334f75'
down_revision: Union[str, Sequence[str], None] = '34e7b92670d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'org_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('org_name', sa.String(length=255), nullable=False),
        sa.Column('timezone', sa.String(length=100), server_default='UTC', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('is_root', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('invite_token_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('invite_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_set', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'password_set')
    op.drop_column('users', 'invite_expires_at')
    op.drop_column('users', 'invite_token_hash')
    op.drop_column('users', 'is_root')
    op.drop_column('users', 'password_hash')
    op.drop_table('org_settings')
