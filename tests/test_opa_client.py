"""Tests for OPA client — decision evaluation."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import app.services.opa_client as opa_client_module
from app.services.opa_client import evaluate


@pytest.fixture(autouse=True)
def _reset_persistent_client():
    """opa_client._client is a persistent module-level singleton (reused across
    calls to avoid a fresh TCP connection per decision) — reset it around every
    test so mocked clients from one test never leak into another."""
    opa_client_module._client = None
    yield
    opa_client_module._client = None


@pytest.mark.asyncio
async def test_evaluate_returns_allow_for_safe_tool():
    """evaluate() must return allow for a tool not on any blacklist."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"decision": "allow", "reason": "default_allow"}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate("safe_tool", {}, [])

    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_evaluate_returns_deny_for_blacklisted_tool():
    """evaluate() must return deny when OPA says deny."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"decision": "deny", "reason": "tool_denylisted"}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate("execute_code", {}, [])

    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_evaluate_reuses_persistent_client_across_calls():
    """evaluate() must not open a new httpx.AsyncClient (new TCP connection)
    on every call — that overhead makes the 20ms decision-timeout budget
    unreliable under any real load. A single persistent client must be reused."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"decision": "allow", "reason": "default_allow"}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await evaluate("tool_one", {}, [])
        await evaluate("tool_two", {}, [])

    assert mock_client_class.call_count == 1


@pytest.mark.asyncio
async def test_warmup_issues_a_real_request_to_establish_the_connection():
    """warmup() must make an actual HTTP call (not just instantiate the
    client) — found via a real clean-container E2E run: the persistent
    client is created lazily on first use, so without a startup warmup the
    very first production request pays TCP-handshake cost inside the same
    decision-timeout budget as evaluation, and can time out."""
    from app.services.opa_client import warmup

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock())
        mock_client_class.return_value = mock_client

        await warmup()

    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_warmup_never_raises_when_opa_is_unreachable():
    """warmup() is best-effort — OPA being down at startup must not crash
    the app; the normal per-request fail-closed/fail-open path still
    applies once real traffic arrives."""
    import httpx as httpx_module
    from app.services.opa_client import warmup

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx_module.ConnectError("refused"))
        mock_client_class.return_value = mock_client

        await warmup()  # must not raise


@pytest.mark.asyncio
async def test_evaluate_includes_reason():
    """evaluate() result must always include a reason field."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"decision": "allow", "reason": "default_allow"}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate("any_tool", {}, [])

    assert "reason" in result
