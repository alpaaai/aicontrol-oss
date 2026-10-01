"""Tests: GET /health reports the in-process engine and gates drift_detector_status."""
import pytest
import app.main as _main
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_reports_the_in_process_engine():
    """Cedar evaluates in this process, so there is no sidecar to poll and no
    unreachable state to report -- the field is a constant now."""
    async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["policy_engine_status"] == "in_process"
    assert "opa_status" not in response.json()


@pytest.mark.asyncio
async def test_health_engine_status_is_not_licence_gated():
    """The engine runs in-process on every tier, so unlike drift detection there
    is nothing to gate -- a community install reports the same value."""
    with patch("app.main.has_enterprise_license", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["policy_engine_status"] == "in_process"


@pytest.mark.asyncio
async def test_health_drift_detector_status_enterprise():
    """Enterprise-plan license → real drift_detector_status returned.

    Gated on the decoded plan (has_enterprise_license), not bare key presence
    (2.5 fix) -- a set-but-undecodable string like "test-key" is not enough,
    unlike before this fix.
    """
    mock_detector = MagicMock()
    mock_detector.status = "healthy"
    _main.app.state.drift_detector = mock_detector

    try:
        with patch("app.main.has_enterprise_license", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
                response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["drift_detector_status"] in ("healthy", "degraded")
    finally:
        del _main.app.state._state["drift_detector"]


@pytest.mark.asyncio
async def test_health_drift_detector_status_community():
    """No license key → drift_detector_status returns enterprise_only."""
    with patch("app.main.has_enterprise_license", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"
