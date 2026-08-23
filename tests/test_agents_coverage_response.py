"""GET /agents surfaces coverage state and unresolved systems.

Deviation from the plan: rows are committed through their own session (the
`db_session` fixture never commits, so the live API the `client` fixture talks
to could not see them) and cleaned up by the existing `test-agent-%` fixture.
"""
import datetime
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.system_resolver import MAX_UNRESOLVED_TRACKED, merge_unresolved


@pytest_asyncio.fixture(loop_scope="session")
async def make_agent():
    """Insert an agent row with arbitrary coverage columns, committed."""
    from app.models.database import async_session_factory

    async def _make(**columns) -> uuid.UUID:
        agent_id = uuid.uuid4()
        columns.setdefault("name", f"test-agent-coverage-{agent_id.hex[:8]}")
        cols = {"id": agent_id, "owner": "tests", "status": "active", **columns}
        names = ", ".join(cols)
        binds = ", ".join(f":{k}" for k in cols)
        async with async_session_factory() as session:
            await session.execute(
                text(f"INSERT INTO agents ({names}) VALUES ({binds})"), cols
            )
            await session.commit()
        return agent_id

    return _make


@pytest.mark.asyncio
async def test_agent_with_handshake_but_no_traffic_reads_installed_not_firing(
    client, admin_token, make_agent
):
    """The state this whole feature exists to surface: the library loaded and
    the hook bound, but no call ever arrived."""
    agent_id = await make_agent(
        framework="langgraph", hook="on_tool_start", sdk_version="0.4.1",
        coverage_last_seen_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    resp = await client.get(f"/agents/{agent_id}", headers=admin_token)
    assert resp.status_code == 200, resp.text
    assert resp.json()["coverage_state"] == "installed_not_firing"


@pytest.mark.asyncio
async def test_agent_with_no_handshake_reads_unknown(client, admin_token, make_agent):
    agent_id = await make_agent()
    resp = await client.get(f"/agents/{agent_id}", headers=admin_token)
    assert resp.json()["coverage_state"] == "unknown"


@pytest.mark.asyncio
async def test_agent_with_traffic_after_the_handshake_reads_governed(
    client, agent_token, admin_token, make_agent
):
    agent_id = await make_agent(
        framework="crewai", hook="before_tool_call", sdk_version="1.0",
        coverage_last_seen_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    intercepted = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(uuid.uuid4()),
        "agent_id": str(agent_id),
        "agent_name": "test-agent-coverage-traffic",
        "tool_name": "read_record",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert intercepted.status_code == 200, intercepted.text

    # allow/deny land in the WAL first and reach Postgres on the shipper's
    # next pass, so give it one.
    import asyncio
    for _ in range(20):
        resp = await client.get(f"/agents/{agent_id}", headers=admin_token)
        if resp.json()["coverage_state"] == "governed":
            break
        await asyncio.sleep(0.1)

    assert resp.json()["coverage_state"] == "governed"


@pytest.mark.asyncio
async def test_silent_noop_warnings_are_returned_verbatim(client, admin_token, make_agent):
    agent_id = await make_agent(
        framework="langgraph", hook="on_tool_start", sdk_version="0.4.1",
        coverage_last_seen_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        silent_noop_warnings='["sync_tool_denial_swallowed:refund_payment"]',
    )
    resp = await client.get(f"/agents/{agent_id}", headers=admin_token)
    assert resp.json()["silent_noop_warnings"] == [
        "sync_tool_denial_swallowed:refund_payment"
    ]


@pytest.mark.asyncio
async def test_the_list_endpoint_carries_coverage_too(client, admin_token, make_agent):
    agent_id = await make_agent(
        framework="langgraph", hook="on_tool_start", sdk_version="0.4.1",
        coverage_last_seen_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        workflow="claims_intake",
    )
    resp = await client.get("/agents", headers=admin_token)
    assert resp.status_code == 200
    row = next(a for a in resp.json() if a["id"] == str(agent_id))
    assert row["coverage_state"] == "installed_not_firing"
    assert row["framework"] == "langgraph"
    assert row["hook"] == "on_tool_start"
    assert row["sdk_version"] == "0.4.1"
    assert row["workflow"] == "claims_intake"
    assert row["unresolved_systems"] == []


@pytest.mark.asyncio
async def test_an_unresolved_system_is_recorded_on_the_agent(
    client, agent_token, admin_token, make_agent
):
    """The 2.2 fail-open mitigation: a policy bound to a system does not match
    a call whose system is unknown, so the unknowns must be visible."""
    agent_id = await make_agent()
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(uuid.uuid4()),
        "agent_id": str(agent_id),
        "agent_name": "test-agent-coverage-unresolved",
        "tool_name": "totally_unmapped_tool",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert resp.status_code == 200, resp.text

    # get_db commits in dependency teardown, which runs *after* the response
    # is sent -- reading straight away races that commit.
    import asyncio
    for _ in range(20):
        detail = await client.get(f"/agents/{agent_id}", headers=admin_token)
        if detail.json()["unresolved_systems"]:
            break
        await asyncio.sleep(0.1)

    assert detail.json()["unresolved_systems"] == ["totally_unmapped_tool"]


# ── merge_unresolved, in isolation ────────────────────────────────────────────

def test_merge_unresolved_appends_a_new_tool():
    assert merge_unresolved(None, "a") == ["a"]
    assert merge_unresolved(["a"], "b") == ["a", "b"]


def test_merge_unresolved_is_distinct():
    assert merge_unresolved(["a"], "a") == ["a"]


def test_merge_unresolved_is_bounded():
    existing = [f"tool_{i}" for i in range(MAX_UNRESOLVED_TRACKED)]
    merged = merge_unresolved(existing, "newest")
    assert len(merged) == MAX_UNRESOLVED_TRACKED
    assert merged[-1] == "newest"
    assert "tool_0" not in merged
