"""Tests: GET /health enterprise gating for opa_status and drift_detector_status."""
import pytest
import app.main as _main
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_opa_status_enterprise():
    """Enterprise license key → real opa_status returned (healthy/degraded/unreachable)."""
    mock_watcher = MagicMock()
    mock_watcher.opa_status = "healthy"
    _main.app.state.opa_watcher = mock_watcher

    try:
        with patch.object(_main._settings, "AICONTROL_LICENSE_KEY", "test-key"):
            async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
                response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["opa_status"] in ("healthy", "degraded", "unreachable")
    finally:
        del _main.app.state._state["opa_watcher"]


@pytest.mark.asyncio
async def test_health_opa_status_community():
    """No license key → opa_status returns enterprise_only."""
    with patch.object(_main._settings, "AICONTROL_LICENSE_KEY", ""):
        async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["opa_status"] == "enterprise_only"


@pytest.mark.asyncio
async def test_health_drift_detector_status_enterprise():
    """Enterprise license key → real drift_detector_status returned."""
    mock_detector = MagicMock()
    mock_detector.status = "healthy"
    _main.app.state.drift_detector = mock_detector

    try:
        with patch.object(_main._settings, "AICONTROL_LICENSE_KEY", "test-key"):
            async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
                response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["drift_detector_status"] in ("healthy", "degraded")
    finally:
        del _main.app.state._state["drift_detector"]


@pytest.mark.asyncio
async def test_health_drift_detector_status_community():
    """No license key → drift_detector_status returns enterprise_only."""
    with patch.object(_main._settings, "AICONTROL_LICENSE_KEY", ""):
        async with AsyncClient(transport=ASGITransport(app=_main.app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"
