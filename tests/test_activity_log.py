"""Tests for user activity log — write_activity_log and GET /dashboard/activity-log."""
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@contextmanager
def _admin_auth_override():
    from app.core.auth import _get_verified_token
    app.dependency_overrides[_get_verified_token] = lambda: {"role": "admin", "email": None}
    try:
        yield
    finally:
        app.dependency_overrides.pop(_get_verified_token, None)


def _opa_patch():
    return patch("app.services.policy_loader.push_rego_to_opa", new=AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_activity_log_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/dashboard/activity-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_policy_update_creates_activity_log(human_admin_token, seed_policy):
    policy_id = seed_policy
    with _admin_auth_override(), _opa_patch():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put(
                f"/policies/{policy_id}",
                json={"description": "Updated via activity log test"},
            )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/activity-log",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert any(l["action"] == "policy.update" for l in logs)
