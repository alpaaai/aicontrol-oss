"""add billing_customers and processed_stripe_events tables

Revision ID: 67febff04874
Revises:
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '67febff04874'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('billing_customers',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
    sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('company', sa.String(length=255), nullable=True),
    sa.Column('plan', sa.String(length=20), nullable=False),
    sa.Column('subscription_status', sa.String(length=20), nullable=False),
    sa.Column('activation_code_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activation_code_hash')
    )
    op.create_table('processed_stripe_events',
    sa.Column('event_id', sa.String(length=255), nullable=False),
    sa.Column('processed_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('event_id')
    )


def downgrade() -> None:
    op.drop_table('processed_stripe_events')
    op.drop_table('billing_customers')
