"""
Tests: opa_client.evaluate() behavior when OPA is unreachable.
These are unit tests — they mock httpx, no real OPA required.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

import app.services.opa_client as opa_client_module
from app.services.opa_client import evaluate


@pytest.fixture(autouse=True)
def _reset_persistent_client():
    """opa_client._client is a persistent module-level singleton — reset it
    around every test so mocked clients from one test never leak into another."""
    opa_client_module._client = None
    yield
    opa_client_module._client = None


@pytest.mark.asyncio
async def test_evaluate_fail_closed_on_connect_error():
    """When OPA is unreachable and OPA_FAILURE_MODE=deny, evaluate() returns deny."""
    with patch("app.services.opa_client.settings") as mock_settings:
        mock_settings.opa_failure_mode = "deny"
        mock_settings.opa_url = "http://localhost:8181"

        with patch("app.services.opa_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            result = await evaluate(
                tool_name="dangerous_tool",
                tool_parameters={},
                policies=[],
                agent_id="test-agent",
            )

    assert result["decision"] == "deny"
    assert result["reason"] == "opa_unavailable"


@pytest.mark.asyncio
async def test_evaluate_fail_open_on_connect_error():
    """When OPA is unreachable and OPA_FAILURE_MODE=allow, evaluate() returns allow."""
    with patch("app.services.opa_client.settings") as mock_settings:
        mock_settings.opa_failure_mode = "allow"
        mock_settings.opa_url = "http://localhost:8181"

        with patch("app.services.opa_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            result = await evaluate(
                tool_name="some_tool",
                tool_parameters={},
                policies=[],
                agent_id="test-agent",
            )

    assert result["decision"] == "allow"
    assert result["reason"] == "opa_unavailable_fail_open"


@pytest.mark.asyncio
async def test_evaluate_fail_closed_on_timeout():
    """Timeout is treated same as connection error — deny when fail-closed."""
    with patch("app.services.opa_client.settings") as mock_settings:
        mock_settings.opa_failure_mode = "deny"
        mock_settings.opa_url = "http://localhost:8181"

        with patch("app.services.opa_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_client_cls.return_value = mock_client

            result = await evaluate(
                tool_name="some_tool",
                tool_parameters={},
                policies=[],
                agent_id="test-agent",
            )

    assert result["decision"] == "deny"
    assert result["reason"] == "opa_unavailable"
