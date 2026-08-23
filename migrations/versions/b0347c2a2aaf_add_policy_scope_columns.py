"""add policy scope columns

Revision ID: b0347c2a2aaf
Revises: 69939d3dc7de
Create Date: 2026-08-22 20:36:32.878832

Adds the Cedar scope columns to `policies`. Additive only.

principal_type is "agent" or "group"; principal_id is that agent's or group's
name. NULL action_tool means "any tool", NULL resource_system means "any system".
effect is "deny" or "review" and supersedes `action`, which stays until task 2.8
migrates the seed policies. cedar_text caches the compiled Cedar source so the
/intercept hot path never recompiles from columns.

Every column is nullable here: existing rows carry no scope until task 2.8, which
tightens principal_type, principal_id and effect to NOT NULL.

ix_policies_scope backs the /intercept pre-filter -- the whole point of scope is
that the engine stops evaluating every policy on every call.

Autogenerate additionally reported drift unrelated to this change (a removed
uq_policies_name constraint, removed tenant_id columns on policies and sessions,
and three removed policy_warnings indexes). None of that is this migration's
business and all of it was stripped: tenant_id is the deliberate unenforced
multi-tenancy seam from decision D7, and dropping it here would break task 7.4.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0347c2a2aaf'
down_revision: Union[str, Sequence[str], None] = '69939d3dc7de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("principal_type", sa.String(length=20), nullable=True))
    op.add_column("policies", sa.Column("principal_id", sa.String(length=100), nullable=True))
    op.add_column("policies", sa.Column("action_tool", sa.String(length=100), nullable=True))
    op.add_column("policies", sa.Column("resource_system", sa.String(length=100), nullable=True))
    op.add_column("policies", sa.Column("effect", sa.String(length=20), nullable=True))
    op.add_column("policies", sa.Column("cedar_text", sa.Text(), nullable=True))
    op.create_index(
        "ix_policies_scope",
        "policies",
        ["active", "principal_type", "principal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_policies_scope", table_name="policies")
    op.drop_column("policies", "cedar_text")
    op.drop_column("policies", "effect")
    op.drop_column("policies", "resource_system")
    op.drop_column("policies", "action_tool")
    op.drop_column("policies", "principal_id")
    op.drop_column("policies", "principal_type")
