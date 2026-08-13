"""Tests for enterprise/app/routers/discovery.py (WS-G, business-tier gated).

Uses ASGITransport (in-process), not the client fixture (live server on
localhost:8001) -- same reasoning as tests/test_mcp_servers_api.py:
unittest.mock.patch and app.dependency_overrides only affect the process
they run in, and both need to actually take effect here.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def _bypass_business_license():
    from app.main import app
    from app.core.license_gate import require_business_license
    app.dependency_overrides[require_business_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_business_license, None)


@pytest.mark.asyncio
async def test_scan_upserts_candidates_and_is_idempotent(admin_token):
    from app.main import app
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    fake_result = [DiscoveredAgentCandidate(
        source="aws_bedrock", external_id="DISCOVERY-API-TEST-1", name="test-discovered-via-api", confidence="high",
    )]
    with patch.object(AWSDiscoveryAdapter, "discover", new=AsyncMock(return_value=fake_result)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/discovery/scan", headers=admin_token)
            second = await client.post("/discovery/scan", headers=admin_token)

    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["status"] == "new"
    assert len(second.json()) == 1
    assert first.json()[0]["id"] == second.json()[0]["id"]


@pytest.mark.asyncio
async def test_promote_creates_a_real_agent(admin_token):
    from app.main import app
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    fake_result = [DiscoveredAgentCandidate(
        source="aws_bedrock", external_id="DISCOVERY-API-TEST-2", name="test-promote-candidate", confidence="high",
    )]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch.object(AWSDiscoveryAdapter, "discover", new=AsyncMock(return_value=fake_result)):
            scan_resp = await client.post("/discovery/scan", headers=admin_token)
        candidate_id = scan_resp.json()[0]["id"]

        promote_resp = await client.post(
            f"/discovery/candidates/{candidate_id}/promote", json={"owner": "security-team"}, headers=admin_token
        )
        assert promote_resp.status_code == 201
        assert promote_resp.json()["name"] == "test-promote-candidate"
        assert promote_resp.json()["owner"] == "security-team"


@pytest.mark.asyncio
async def test_promote_rejects_missing_owner(admin_token):
    from app.main import app
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    fake_result = [DiscoveredAgentCandidate(
        source="aws_bedrock", external_id="DISCOVERY-API-TEST-4", name="test-promote-no-owner", confidence="high",
    )]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch.object(AWSDiscoveryAdapter, "discover", new=AsyncMock(return_value=fake_result)):
            scan_resp = await client.post("/discovery/scan", headers=admin_token)
        candidate_id = scan_resp.json()[0]["id"]

        promote_resp = await client.post(
            f"/discovery/candidates/{candidate_id}/promote", json={"owner": ""}, headers=admin_token
        )
        assert promote_resp.status_code == 422

        list_resp = await client.get("/discovery/candidates", headers=admin_token)

    unpromoted = next(c for c in list_resp.json() if c["id"] == candidate_id)
    assert unpromoted["status"] == "new"
    assert unpromoted["promoted_agent_id"] is None


@pytest.mark.asyncio
async def test_dismiss_marks_candidate_dismissed(admin_token):
    from app.main import app
    from enterprise.app.services.discovery.port import DiscoveredAgentCandidate
    from enterprise.app.services.discovery.aws_adapter import AWSDiscoveryAdapter

    fake_result = [DiscoveredAgentCandidate(
        source="aws_bedrock", external_id="DISCOVERY-API-TEST-3", name="test-dismiss-candidate", confidence="low",
    )]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch.object(AWSDiscoveryAdapter, "discover", new=AsyncMock(return_value=fake_result)):
            scan_resp = await client.post("/discovery/scan", headers=admin_token)
        candidate_id = scan_resp.json()[0]["id"]

        dismiss_resp = await client.post(f"/discovery/candidates/{candidate_id}/dismiss", headers=admin_token)
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_scan_requires_admin(agent_token):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/discovery/scan", headers=agent_token)
    assert resp.status_code == 403
