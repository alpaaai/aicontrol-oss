"""Replay a draft against eligible recent traffic and report an outcome.

Uses ASGITransport (in-process) -- same reasoning as
test_policy_authoring_router.py and test_nl_draft_scoped.py: the live
localhost server fixture does not see edits made in this worktree/process.

This runs against a shared dev Postgres database that already carries real
seed/demo audit events with workflow set, so exact-count assertions against
the whole table are unreliable. Assertions below are either deltas around a
baseline call, or scoped to the fixture's own row ids.
"""
import datetime
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

DRAFT = {
    "principal_type": "agent", "principal_id": "claims-adjuster",
    "action_tool": "release_payment", "resource_system": "guidewire",
    "effect": "review",
    "condition": {"numeric_conditions": {"amount": {"gt": 50000}}},
}

# agent_name is set to the draft's own principal_id ("claims-adjuster") so
# the fixture rows actually match the scope under test. Rows are tagged for
# cleanup via a "_fixture" key inside tool_parameters instead, since the
# agent name itself is part of what's being tested.
_FIXTURE_TAG = "nl-simulation-fixture"


@pytest.fixture(autouse=True)
def _bypass_enterprise_license():
    from app.main import app
    from app.core.license_gate import require_enterprise_license
    app.dependency_overrides[require_enterprise_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_enterprise_license, None)


async def _post_simulate(admin_token, draft, window_days=7):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/policies/simulate",
            json={"draft": draft, "window_days": window_days},
            headers=admin_token,
        )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_simulation_events():
    """Session setup + teardown: remove this file's tagged rows so a prior
    interrupted run can't corrupt the delta assertions below."""
    from app.models.database import async_session_factory
    from sqlalchemy import text

    async def _delete():
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM audit_events WHERE tool_parameters->>'_fixture' = :tag"),
                {"tag": _FIXTURE_TAG},
            )
            await db.commit()

    await _delete()
    yield
    await _delete()


async def _insert_events() -> list[uuid.UUID]:
    """409 non-matching + 3 matching (release_payment/guidewire/amount>50000)
    rows, all tagged with _FIXTURE_TAG so cleanup can find them."""
    from app.models.database import async_session_factory
    from sqlalchemy import text

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    ids: list[uuid.UUID] = []
    async with async_session_factory() as db:
        for i in range(409):
            eid = uuid.uuid4()
            ids.append(eid)
            await db.execute(text("""
                INSERT INTO audit_events
                    (id, sequence_number, tool_name, tool_parameters, decision, workflow, agent_name, created_at)
                VALUES
                    (:id, :seq, 'read_claim', CAST(:params AS jsonb), 'allow', 'claims_intake', :agent, :created_at)
            """), {"id": str(eid), "seq": i,
                    "params": json.dumps({"system": "guidewire", "claim_id": str(i), "_fixture": _FIXTURE_TAG}),
                    "agent": "claims-adjuster", "created_at": now})
        for i in range(3):
            eid = uuid.uuid4()
            ids.append(eid)
            await db.execute(text("""
                INSERT INTO audit_events
                    (id, sequence_number, tool_name, tool_parameters, decision, workflow, agent_name, created_at)
                VALUES
                    (:id, :seq, 'release_payment', CAST(:params AS jsonb), 'allow', 'claims_intake', :agent, :created_at)
            """), {"id": str(eid), "seq": 1000 + i,
                    "params": json.dumps({"system": "guidewire", "amount": 75000, "_fixture": _FIXTURE_TAG}),
                    "agent": "claims-adjuster", "created_at": now})
        await db.commit()
    return ids


async def _delete_events(ids: list[uuid.UUID]) -> None:
    from app.models.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        for eid in ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.commit()


@pytest.mark.asyncio
async def test_simulation_counts_only_matching_calls(admin_token):
    baseline = (await _post_simulate(admin_token, DRAFT)).json()
    ids = await _insert_events()
    try:
        after = (await _post_simulate(admin_token, DRAFT)).json()
    finally:
        await _delete_events(ids)

    assert after["eligible_events"] - baseline["eligible_events"] == 412
    assert after["would_review"] - baseline["would_review"] == 3
    assert after["would_deny"] == baseline["would_deny"]


@pytest.mark.asyncio
async def test_matching_events_are_returned_for_inspection(admin_token):
    ids = await _insert_events()
    try:
        resp = await _post_simulate(admin_token, DRAFT)
    finally:
        await _delete_events(ids)

    matches = resp.json()["matches"]
    fixture_ids = set(ids)
    fixture_matches = [m for m in matches if uuid.UUID(m["audit_event_id"]) in fixture_ids]
    assert len(fixture_matches) == 3
    assert all(m["tool_name"] == "release_payment" for m in fixture_matches)


@pytest.mark.asyncio
async def test_pre_cutover_events_are_excluded_from_the_corpus(admin_token):
    """An event with no workflow predates identity capture and cannot be
    replayed against a scoped draft."""
    from app.models.database import async_session_factory
    from sqlalchemy import text

    before = (await _post_simulate(admin_token, DRAFT)).json()["eligible_events"]

    eid = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO audit_events
                (id, sequence_number, tool_name, tool_parameters, decision, workflow, agent_name, created_at)
            VALUES
                (:id, 1, 'release_payment', CAST(:params AS jsonb), 'allow', NULL, :agent, NOW())
        """), {"id": str(eid),
                "params": json.dumps({"amount": 90000, "_fixture": _FIXTURE_TAG}),
                "agent": "claims-adjuster"})
        await db.commit()

    try:
        after = (await _post_simulate(admin_token, DRAFT)).json()["eligible_events"]
        assert after == before
    finally:
        async with async_session_factory() as db:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
            await db.commit()


@pytest.mark.asyncio
async def test_empty_corpus_says_so_instead_of_reporting_zero(admin_token):
    # window_days=0 sets the cutoff to "now" -- any pre-existing seed/demo
    # data in this shared dev database was created in the past and is
    # excluded, guaranteeing a genuinely empty corpus regardless of what
    # else lives in the table.
    resp = await _post_simulate(admin_token, DRAFT, window_days=0)
    body = resp.json()
    assert body["eligible_events"] == 0
    assert body["would_review"] is None
    assert body["would_deny"] is None
    assert "no traffic" in body["corpus_note"].lower()


async def _count(model) -> int:
    from app.models.database import async_session_factory
    from sqlalchemy import func, select

    async with async_session_factory() as db:
        return (await db.execute(select(func.count(model.id)))).scalar_one()


@pytest.mark.asyncio
async def test_simulation_never_writes_a_policy(admin_token):
    from app.models.schemas import Policy
    ids = await _insert_events()
    try:
        before = await _count(Policy)
        await _post_simulate(admin_token, DRAFT)
        after = await _count(Policy)
    finally:
        await _delete_events(ids)
    assert after == before


@pytest.mark.asyncio
async def test_simulation_never_writes_an_audit_event(admin_token):
    from app.models.schemas import AuditEvent
    ids = await _insert_events()
    try:
        before = await _count(AuditEvent)
        await _post_simulate(admin_token, DRAFT)
        after = await _count(AuditEvent)
    finally:
        await _delete_events(ids)
    assert after == before
