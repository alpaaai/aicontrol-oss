"""Tests for app/services/billing_client.py -- server-to-server calls from
the customer instance to billing-service (plans/v4 task 18)."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.billing_client import BillingClientError, fetch_billing_urls, sync_license


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    return resp


@pytest.mark.asyncio
async def test_fetch_billing_urls_happy_path_returns_manage_subscription_url():
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(200, {"url": "https://billing.stripe.com/session/abc"})
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_billing_urls("test-activation-code", "business")

    assert result["manage_subscription_url"] == "https://billing.stripe.com/session/abc"
    assert result["upgrade_url"] is None
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args.args[0].endswith("/billing/portal")
    assert call_args.kwargs["json"] == {"activation_code": "test-activation-code"}


@pytest.mark.asyncio
async def test_fetch_billing_urls_trial_plan_includes_upgrade_url():
    portal_response = _mock_response(200, {"url": "https://billing.stripe.com/session/abc"})
    upgrade_response = _mock_response(200, {"url": "https://checkout.stripe.com/session/xyz"})
    mock_client = AsyncMock()
    mock_client.post.side_effect = [portal_response, upgrade_response]
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_billing_urls("test-activation-code", "trial")

    assert result["manage_subscription_url"] == "https://billing.stripe.com/session/abc"
    assert result["upgrade_url"] == "https://checkout.stripe.com/session/xyz"
    assert mock_client.post.call_count == 2
    upgrade_call = mock_client.post.call_args_list[1]
    assert upgrade_call.args[0].endswith("/billing/upgrade")
    assert upgrade_call.kwargs["json"] == {"activation_code": "test-activation-code", "plan": "business"}


@pytest.mark.asyncio
async def test_fetch_billing_urls_trial_plan_degrades_to_no_upgrade_url_on_upgrade_failure():
    portal_response = _mock_response(200, {"url": "https://billing.stripe.com/session/abc"})
    upgrade_response = _mock_response(429, {"detail": "rate limited"})
    mock_client = AsyncMock()
    mock_client.post.side_effect = [portal_response, upgrade_response]
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_billing_urls("test-activation-code", "trial")

    assert result["manage_subscription_url"] == "https://billing.stripe.com/session/abc"
    assert result["upgrade_url"] is None


@pytest.mark.asyncio
async def test_fetch_billing_urls_raises_billing_client_error_on_timeout():
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectTimeout("connect timed out")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BillingClientError):
            await fetch_billing_urls("test-activation-code", "business")


@pytest.mark.asyncio
async def test_fetch_billing_urls_raises_billing_client_error_on_non_200():
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(401, {"detail": "invalid activation code"})
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BillingClientError):
            await fetch_billing_urls("bad-code", "business")


@pytest.mark.asyncio
async def test_sync_license_happy_path_returns_status_and_plan():
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(200, {"status": "active", "plan": "business"})
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        result = await sync_license("test-activation-code")

    assert result == {"status": "active", "plan": "business"}
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args.args[0].endswith("/license/sync")
    assert call_args.kwargs["headers"] == {"Authorization": "Bearer test-activation-code"}


@pytest.mark.asyncio
async def test_sync_license_raises_billing_client_error_on_connection_error():
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("connection refused")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BillingClientError):
            await sync_license("test-activation-code")


@pytest.mark.asyncio
async def test_sync_license_raises_billing_client_error_on_401():
    mock_client = AsyncMock()
    mock_client.get.return_value = _mock_response(401, {"detail": "invalid activation code"})
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.billing_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BillingClientError):
            await sync_license("bad-code")
