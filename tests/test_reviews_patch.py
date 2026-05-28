"""Tests for PATCH /reviews/{id} approve/deny."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_patch_review_approve(human_admin_token, seed_pending_review):
    review_id = seed_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "approve", "note": "Looks fine"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_patch_review_deny(human_admin_token, seed_pending_review):
    review_id = seed_pending_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/reviews/{review_id}",
            json={"action": "deny", "note": "Policy violation"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_patch_review_invalid_action(human_admin_token, seed_pending_review):
    review_id = seed_pending_review
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
