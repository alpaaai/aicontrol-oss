"""Tests for PATCH /reviews/{id} approve/deny."""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(loop_scope="session")
async def fresh_pending_review():
    """Function-scoped, unlike the session-scoped seed_pending_review fixture --
    each test needs its own untouched 'pending' row now that PATCH only allows
    a single resolution (see test_patch_review_already_resolved_returns_409)."""
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


@pytest.mark.asyncio
async def test_patch_review_approve(human_admin_token, fresh_pending_review):
    review_id = fresh_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "approve", "note": "Looks fine"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_patch_review_deny(human_admin_token, fresh_pending_review):
    review_id = fresh_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "deny", "note": "Policy violation"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_patch_review_invalid_action(human_admin_token, fresh_pending_review):
    review_id = fresh_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "delete"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_review_not_found(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/reviews/00000000-0000-0000-0000-000000000000",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_review_already_resolved_returns_409(human_admin_token, fresh_pending_review):
    """A review that has already been resolved (approved/denied) must reject a
    second PATCH rather than silently overwriting the prior decision."""
    review_id = fresh_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "deny", "note": "Policy violation"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
        assert first.status_code == 200

        second = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "approve", "note": "actually fine"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )

    assert second.status_code == 409
    assert second.json()["detail"] == "Review already resolved"
