"""Canonical sweep of test/demo-artifact rows.

Single source of truth for what counts as a leaked test row and how to
clean it up. Used by tests/conftest.py's autouse cleanup fixtures and by
the standalone `scripts/db_hygiene_check.py` CLI, so the two never drift
out of sync the way the old per-table fixtures did.

Convention: any row created by a test or a manual dev/demo run must be
named so it matches one of the SWEEPS patterns below --

    agents.name           LIKE 'test-agent-%'
    policies.name          LIKE 'test_%' OR LIKE 'not_lib_%'
    discovered_agents.external_id  LIKE 'DISCOVERY-API-TEST-%'
    agents.name (discovery) IN (exact names below)
    api_tokens.description LIKE 'pytest-%'

Adding a new kind of test-created row means adding a sweep here, not
inventing a new prefix and a bespoke fixture elsewhere.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Sweep:
    label: str
    count_sql: str
    clean: Callable[[AsyncSession], Awaitable[None]]


async def _clean_agents(session: AsyncSession) -> None:
    # sessions.agent_id, audit_events.agent_id/session_id, hitl_reviews.session_id,
    # api_tokens.agent_id and discovered_agents.promoted_agent_id are all NO ACTION
    # FKs onto agents.id -- a bare DELETE raises ForeignKeyViolationError the
    # moment a test agent has driven a real intercept or been promoted from a
    # discovery row. audit_events is append-only, so its rows are never deleted:
    # the nullable FK columns are cleared instead.
    await session.execute(text(
        "UPDATE audit_events SET agent_id = NULL, agent_name = NULL "
        "WHERE agent_id IN (SELECT id FROM agents WHERE name LIKE 'test-agent-%')"
    ))
    await session.execute(text(
        "UPDATE audit_events SET agent_name = NULL WHERE agent_name LIKE 'test-agent-%'"
    ))
    await session.execute(text(
        "UPDATE audit_events SET session_id = NULL WHERE session_id IN "
        "(SELECT id FROM sessions WHERE agent_id IN "
        "(SELECT id FROM agents WHERE name LIKE 'test-agent-%'))"
    ))
    await session.execute(text(
        "UPDATE hitl_reviews SET session_id = NULL WHERE session_id IN "
        "(SELECT id FROM sessions WHERE agent_id IN "
        "(SELECT id FROM agents WHERE name LIKE 'test-agent-%'))"
    ))
    await session.execute(text(
        "DELETE FROM sessions WHERE agent_id IN "
        "(SELECT id FROM agents WHERE name LIKE 'test-agent-%')"
    ))
    await session.execute(text(
        "DELETE FROM admission_scans WHERE agent_id IN "
        "(SELECT id FROM agents WHERE name LIKE 'test-agent-%')"
    ))
    await session.execute(text(
        "UPDATE discovered_agents SET promoted_agent_id = NULL "
        "WHERE promoted_agent_id IN (SELECT id FROM agents WHERE name LIKE 'test-agent-%')"
    ))
    await session.execute(text(
        "DELETE FROM api_tokens WHERE agent_id IN "
        "(SELECT id FROM agents WHERE name LIKE 'test-agent-%')"
    ))
    await session.execute(text("DELETE FROM agents WHERE name LIKE 'test-agent-%'"))


_DISCOVERY_AGENT_NAMES = (
    "test-discovered-via-api",
    "test-promote-candidate",
    "test-promote-no-owner",
    "test-dismiss-candidate",
)


async def _clean_policies(session: AsyncSession) -> None:
    await session.execute(text(
        "UPDATE audit_events SET policy_id = NULL, policy_name = NULL "
        "WHERE policy_id IN (SELECT id FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%')"
    ))
    await session.execute(text(
        "UPDATE audit_events SET policy_name = NULL "
        "WHERE policy_name LIKE 'test_%' OR policy_name LIKE 'not_lib_%'"
    ))
    await session.execute(text(
        "DELETE FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%'"
    ))


async def _clean_discovery(session: AsyncSession) -> None:
    # discovered_agents.promoted_agent_id FKs to agents.id -- clear/delete the
    # child rows before the agents delete below or it violates the FK.
    await session.execute(text(
        "DELETE FROM discovered_agents WHERE external_id LIKE 'DISCOVERY-API-TEST-%'"
    ))
    await session.execute(text(
        "DELETE FROM agents WHERE name = ANY(:names)"
    ), {"names": list(_DISCOVERY_AGENT_NAMES)})


async def _clean_tokens(session: AsyncSession) -> None:
    await session.execute(text(
        "DELETE FROM api_tokens WHERE description LIKE 'pytest-%'"
    ))


SWEEPS = [
    Sweep(
        label="agents",
        count_sql=(
            "SELECT (SELECT count(*) FROM agents WHERE name LIKE 'test-agent-%')"
            " + (SELECT count(*) FROM audit_events WHERE agent_name LIKE 'test-agent-%')"
        ),
        clean=_clean_agents,
    ),
    Sweep(
        label="policies",
        count_sql=(
            "SELECT (SELECT count(*) FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%')"
            " + (SELECT count(*) FROM audit_events WHERE policy_name LIKE 'test_%' OR policy_name LIKE 'not_lib_%')"
        ),
        clean=_clean_policies,
    ),
    Sweep(
        label="discovered_agents",
        count_sql=(
            "SELECT (SELECT count(*) FROM discovered_agents WHERE external_id LIKE 'DISCOVERY-API-TEST-%')"
            " + (SELECT count(*) FROM agents WHERE name IN "
            "('test-discovered-via-api', 'test-promote-candidate', 'test-promote-no-owner', 'test-dismiss-candidate'))"
        ),
        clean=_clean_discovery,
    ),
    Sweep(
        label="api_tokens",
        count_sql="SELECT count(*) FROM api_tokens WHERE description LIKE 'pytest-%'",
        clean=_clean_tokens,
    ),
]


async def count_leaked(session: AsyncSession) -> dict[str, int]:
    """Report leaked-row counts per sweep, without deleting anything."""
    counts = {}
    for sweep in SWEEPS:
        result = await session.execute(text(sweep.count_sql))
        counts[sweep.label] = result.scalar_one()
    return counts


async def clean_all(session: AsyncSession) -> dict[str, str]:
    """Run every sweep, committing after each so one failure can't roll
    back or block the others. Returns {label: error_message} for any
    sweep that raised -- empty if all sweeps succeeded."""
    errors: dict[str, str] = {}
    for sweep in SWEEPS:
        try:
            await sweep.clean(session)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            errors[sweep.label] = str(exc)
    return errors
