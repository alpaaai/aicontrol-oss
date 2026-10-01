"""Tests for the cross-channel HITL resolution race: concurrent PATCH
/reviews/{id} calls (and PATCH racing a Slack handle_action call) on the same
review must not both succeed -- exactly one resolution should win, the other
must observe the row as already resolved."""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.core.license_gate import require_business_license
from app.main import app
from app.models.database import async_session_factory


@pytest.fixture(autouse=True)
def _bypass_business_license_gate():
    app.dependency_overrides[require_business_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_business_license, None)


@pytest_asyncio.fixture(loop_scope="session")
async def fresh_pending_review():
    review_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text(
            "INSERT INTO hitl_reviews (id, status, created_at) VALUES (:id, 'pending', NOW())"
        ), {"id": str(review_id)})
        await db.commit()
    yield review_id
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(review_id)})
        await db.commit()


async def _patch(client: AsyncClient, review_id: uuid.UUID, action: str, token: str):
    return await client.patch(
        f"/reviews/{review_id}",
        json={"action": action, "note": f"via {action}"},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_concurrent_action_review_only_one_wins(human_admin_token, fresh_pending_review):
    """Two concurrent PATCH /reviews/{id} calls on the same pending review
    must not both return 200 -- exactly one succeeds, the other must see the
    row as already resolved (409), never silently overwrite the winner."""
    review_id = fresh_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        results = await asyncio.gather(
            _patch(client, review_id, "approve", human_admin_token),
            _patch(client, review_id, "deny", human_admin_token),
        )

    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 409], (
        f"expected exactly one 200 and one 409, got {[r.status_code for r in results]}"
    )

    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT status FROM hitl_reviews WHERE id = :id"), {"id": str(review_id)}
        )).mappings().one()
    assert row["status"] in ("approved", "denied")


@pytest.mark.asyncio
async def test_concurrent_slack_and_dashboard_resolution_only_one_wins(
    human_admin_token, fresh_pending_review
):
    """A Slack approve racing a dashboard PATCH on the same review must not
    both apply -- one wins, the other's write must be a no-op, never a
    silent overwrite of the first resolution."""
    from app.routers.slack_actions import handle_action

    review_id = fresh_pending_review

    async def _slack_resolve():
        async with async_session_factory() as session:
            await handle_action(
                session=session,
                action_id="hitl_deny",
                review_id=review_id,
                reviewer="U999",
            )
            await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        dashboard_task = _patch(client, review_id, "approve", human_admin_token)
        results = await asyncio.gather(dashboard_task, _slack_resolve())

    dashboard_resp = results[0]

    async with async_session_factory() as session:
        row = (await session.execute(
            text("SELECT status, reviewer FROM hitl_reviews WHERE id = :id"),
            {"id": str(review_id)},
        )).mappings().one()

    if dashboard_resp.status_code == 200:
        assert row["status"] == "approved"
    else:
        assert dashboard_resp.status_code == 409
        assert row["status"] == "denied"
        assert row["reviewer"] == "U999"
