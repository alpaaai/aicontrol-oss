"""Tests: GET /health includes opa_status field."""
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
