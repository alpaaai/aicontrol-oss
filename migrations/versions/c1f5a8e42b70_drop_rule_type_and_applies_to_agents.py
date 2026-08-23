"""drop rule_type, action and applies_to_agents

Revision ID: c1f5a8e42b70
Revises: b0347c2a2aaf
Create Date: 2026-08-22 21:05:00.000000

Completes the move to the Cedar scope model.

C7: applies_to_agents was a half-built binding table that the scope columns
supersede. Single-agent entries migrate to an agent-scoped policy before the
column drops. Verified on this database at migration time: **no policy row had a
non-empty applies_to_agents**, so the UPDATE below was a no-op here. It is kept
so the migration is correct against any deployment that does carry bindings.
Multi-agent entries are deliberately NOT auto-converted -- one row cannot express
several principals, and the choice between "N agent-scoped rows" and "one
group-scoped row" is a per-policy judgement, not something a migration should
guess. Any such row is left with a NULL principal, which reads as "every agent",
and must be reviewed by hand.

rule_type and action are dropped rather than ported (C4): Rego needed the
rule_type dispatch, Cedar does not -- the presence of a key in `condition` is the
dispatch. `action` is superseded by `effect`, which carries deny/review; the
third value, allow, is no longer a policy at all but the catch-all permit
cedar_client appends to every bundle.

effect tightens to NOT NULL. principal_type and principal_id stay nullable on
purpose: NULL principal is the "applies to every agent" case that
get_scoped_policies matches with an IS NULL branch, which avoids inventing a
magic "all" group.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f5a8e42b70'
down_revision: Union[str, Sequence[str], None] = 'b0347c2a2aaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE policies
        SET principal_type = 'agent',
            principal_id = applies_to_agents->>0
        WHERE principal_id IS NULL
          AND jsonb_array_length(COALESCE(applies_to_agents, '[]'::jsonb)) = 1
    """)
    # Rows predating the scope columns have no effect; default them to deny
    # before the NOT NULL, matching the fail-closed posture everywhere else.
    op.execute("UPDATE policies SET effect = 'deny' WHERE effect IS NULL")

    op.drop_column("policies", "applies_to_agents")
    op.drop_column("policies", "rule_type")
    op.drop_column("policies", "action")
    op.alter_column("policies", "effect", nullable=False)


def downgrade() -> None:
    op.alter_column("policies", "effect", nullable=True)
    op.add_column("policies", sa.Column("action", sa.String(length=20), nullable=True))
    op.add_column("policies", sa.Column("rule_type", sa.String(length=50), nullable=True))
    op.add_column(
        "policies",
        sa.Column("applies_to_agents", sa.dialects.postgresql.JSONB(), server_default="[]"),
    )
    # The original rule_type and action values are not recoverable -- this
    # downgrade restores the columns, not their contents.
    op.execute("UPDATE policies SET action = effect WHERE action IS NULL")
