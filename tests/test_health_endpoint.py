"""Tests: GET /health includes opa_status and drift_detector_status fields."""
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_opa_status():
    """GET /health response must include opa_status field."""
    mock_watcher = MagicMock()
    mock_watcher.opa_status = "healthy"
    app.state.opa_watcher = mock_watcher

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "opa_status" in data
        assert data["opa_status"] == "healthy"
    finally:
        del app.state.opa_watcher


@pytest.mark.asyncio
async def test_health_includes_drift_detector_status():
    """GET /health response must include drift_detector_status field."""
    mock_detector = MagicMock()
    mock_detector.status = "healthy"
    app.state.drift_detector = mock_detector

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "drift_detector_status" in data
        assert data["drift_detector_status"] in ("healthy", "degraded", "unknown")
    finally:
        del app.state.drift_detector
