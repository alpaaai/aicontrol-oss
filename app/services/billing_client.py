"""Server-to-server calls from this customer instance to billing-service
(plans/v4 task 18). Single place all outbound calls to billing.aictl.io go
through -- used by billing_usage() (task 19), the trial upgrade endpoint,
and the daily license sync job (task 20).
"""
from __future__ import annotations

import httpx

from app.core.config import settings

_TIMEOUT = httpx.Timeout(5.0, connect=5.0)


class BillingClientError(Exception):
    """Raised when billing-service is unreachable or returns an error
    response. Callers must catch this rather than letting a bare
    httpx.RequestError leak through."""
    pass


async def fetch_billing_urls(activation_code: str) -> dict:
    """Manage-subscription URL for an existing billing-service customer,
    via POST /billing/portal keyed on the org's stored activation code."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            portal_response = await client.post(
                f"{settings.AICONTROL_LICENSE_SYNC_URL}/billing/portal",
                json={"activation_code": activation_code},
            )
    except httpx.RequestError as exc:
        raise BillingClientError(f"billing-service unreachable: {exc}") from exc

    if portal_response.status_code != 200:
        raise BillingClientError(f"billing-service returned {portal_response.status_code}")

    return {"manage_subscription_url": portal_response.json()["url"]}


async def create_upgrade_checkout(activation_code: str, plan: str) -> str:
    """Checkout URL for a mid-trial upgrade to business or enterprise, via
    billing-service's POST /billing/upgrade (trial customers only). Called
    when the admin clicks an upgrade button, not on every Billing page
    load, so no Checkout Session is created unless one is wanted."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.AICONTROL_LICENSE_SYNC_URL}/billing/upgrade",
                json={"activation_code": activation_code, "plan": plan},
            )
    except httpx.RequestError as exc:
        raise BillingClientError(f"billing-service unreachable: {exc}") from exc

    if response.status_code != 200:
        raise BillingClientError(f"billing-service returned {response.status_code}")

    return response.json()["url"]


async def sync_license(activation_code: str) -> dict:
    """GET /license/sync, activation code as bearer token. Returns
    {"status": ..., "plan": ...}."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{settings.AICONTROL_LICENSE_SYNC_URL}/license/sync",
                headers={"Authorization": f"Bearer {activation_code}"},
            )
    except httpx.RequestError as exc:
        raise BillingClientError(f"billing-service unreachable: {exc}") from exc

    if response.status_code != 200:
        raise BillingClientError(f"billing-service returned {response.status_code}")

    return response.json()
